
import asyncio
import logging
import os
import re
import sys
import time

import tornado.ioloop
import tornado.gen

import aiosqlite
import sqlite3

import webwg

logging.getLogger("aiosqlite").setLevel(logging.WARNING)


class Database:
    def __init__(self):
        params = dict(webwg.config.items('database'))
        self.path = params['path']

class Sync(Database):
    def open(self):
        try:
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
        except sqlite3.OperationalError:
            raise webwg.error('Unable to open database: %s', self.path) from None

        self.conn.text_factory = str
        self.conn.row_factory  = sqlite3.Row

        self.conn.execute('PRAGMA foreign_keys = ON;')

    def __del__(self):
        self.close()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def initialize(self):
        schema = os.path.join(webwg.root, 'database', 'webwg.sql')
        try:
            script = open(schema, 'r').read()
        except:
            raise webwg.error('Could not open WebWG SQL script: %s', schema) from None

        cursor = self.conn.cursor()
        cursor.executescript(script)
        cursor.close()

    def list_servers(self):
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT * FROM servers'''
            )

        servers = {}
        results = cursor.fetchall()
        for result in results:
            result = dict(result)
            servers[result['interface']] = result

        cursor.close()
        return servers

    def list_users(self):
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT * FROM users'''
            )

        users = cursor.fetchall()
        for user in users:
            print(f"{user['username']} / {time.ctime(user['created'] / 1000)}")

        cursor.close()

    def user(self, username, password):
        password = webwg.crypto.simple_hash(username + password)

        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT OR REPLACE INTO users VALUES (?,?,false,?,0);''',
            (username, password, int(time.time()*1000))
            )
        cursor.close()
        self.conn.commit()


class Async(Database):
    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.text_factory = str
        self.conn.row_factory  = sqlite3.Row
        cursor = await self.conn.cursor()
        await cursor.execute('PRAGMA foreign_keys = ON;')
        await cursor.close()

    async def close(self):
        await self.conn.commit()
        await self.conn.close()
        webwg.loop.add_callback(webwg.loop.stop)

    async def statement(self, statement, *args):
        cursor = await self.conn.cursor()
        await cursor.execute(statement, args)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def find(self, table, params=None, sort=None):
        statement = 'SELECT * FROM {0}'.format(table)
        if params:
            statement += ' WHERE ' + params
        if sort:
            statement += ' ' + sort
        cursor = await self.conn.cursor()
        await cursor.execute(statement)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows
        #return list(dict(row) for row in rows)

    async def findOne(self, table, col, value):
        statement = 'SELECT * FROM {0} WHERE {1}=?'.format(table, col)
        cursor = await self.conn.cursor()
        await cursor.execute(statement, (value,))
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def insert(self, table, values, id_column='id'):
        cols = ','.join('"%s"' % s for s in values.keys())
        placeholder = ','.join('?' * len(values))
        statement = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(table, cols, placeholder)

        cursor = await self.conn.cursor()
        try:
            await cursor.execute(statement, list(values.values()))
            if id_column not in values:
                values[id_column] = cursor.lastrowid
        except sqlite3.ProgrammingError as e:
            raise webwg.error('Problem executing statement: %s', e)
        except sqlite3.IntegrityError as e:
            raise webwg.error('Integrity error: %s', e)
        finally:
            await cursor.close()
        await self.conn.commit()

    async def update(self, table, values, id_column='id'):
        _id = values[id_column]
        columns = ','.join('"%s"=?' % s for s in values.keys())
        statement = 'UPDATE {0} SET {1} WHERE {2}=?'.format(table, columns, id_column)
        cursor = await self.conn.cursor()
        try:
            await cursor.execute(statement, list(values.values()) + [_id])
        except sqlite3.ProgrammingError as e:
            raise webwg.error('Problem executing statement: %s', e)
        except sqlite3.IntegrityError as e:
            raise webwg.error('Integrity error: %s', e)
        finally:
            await cursor.close()
        await self.conn.commit()

    async def delete(self, table, value, col='id'):
        statement = 'DELETE FROM {0} WHERE {1} = ?'.format(table, col)
        cursor = await self.conn.cursor()
        await cursor.execute(statement, (value,))
        await cursor.close()
        await self.conn.commit()
