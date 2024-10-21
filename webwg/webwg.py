
import collections
import dataclasses
import json
import logging
import os
import subprocess
import sys
import time
import uuid

import _

import webwg

from . import handlers

# this will change the default authentication behavior
# for all the handlers associated with the loaded components
# must be set before _.settings.load is called
_.auth.protected = _.auth.filter_user(lambda current_user: current_user)

class WebWg(_.Application):
    async def initialize(self):
        self.websockets = {}
        self.interfaces = {}
        
        for server in await _.sqlite.find(_.data.servers):
            self.create(server)

        for peer in await _.sqlite.find(_.data.peers):
            self.add(peer)

        self.patterns = [
            #( r'/config/(.*)',   handlers.Config     ),
            #( r'/qr/(.*)',       handlers.QR         ),
            ( r'/ws',       webwg.handlers.Socket, { 'websockets' : self.websockets } ),
            ( r'/([a-z]*)', _.handlers.Protected ),
            ]

        #self.status_task  = self.periodic(10, self.status)
        #self.status_task.cancel()

    async def broadcast(self, msg):
        'Broadcast a message to all connected sockets'
        for ws in self.websockets.values():
            ws.write_message(msg)

    async def status(self):
        logging.info('Periodic: %s', time.ctime())

    async def on_dblogin_add_user(self, name, user):
        'make adjustments to the record before calling sql statement'
        user.disabled = False
        user.isadmin  = True
        user.created  = _.now()
        await self.broadcast(dict(action='add', collection='users', data=user._as_dict()))

    async def on_dbcache_delete(self, component, session_id):
        'allow apps to make adjustments to the record before calling sql statement'
        print('on_dbcache_delete', component, session_id)
        print()
        await self.broadcast(dict(action='delete', collection='sessions', id=session_id))

    async def on_login(self, handler, user):
        user.last = int(time.time() * 1000)
        await _.sqlite.upsert(user)

        session = {
            'session_id' : str(uuid.uuid4()),
            'username'   : user.username,
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        return session

    async def is_session_expired(self, session, expires):
        created = session['time'] / 1000
        elapsed = (time.time() - created) / 3600
        return elapsed > expires

    def create(self, server):
        self.interfaces[server.instance] = server.interface
        logging.info('Creating wireguard inteface: %s: %s', server.interface, f'{server.network}/24')
        WebWg.ip('link','add', server.interface, 'type', 'wireguard')
        WebWg.ip('address','add', 'dev', server.interface, f'{server.network}/24')
        WebWg.wg('set', server.interface,
            'listen-port', f'{server.port}',
            'private-key', '/dev/stdin',
            stdin=server.priv
            )
        WebWg.ip('link','set', 'up', 'dev', server.interface)

    def add(self, peer):
        try:
            interface = self.interfaces[peer.instance]
        except KeyError:
            logging.error('No interface!')
            return
        logging.info('Adding wireguard peer: %s: %s: %s', interface, peer.name, f'{peer.address}')
        WebWg.wg('set', interface,
            'peer', peer.pub,
            'preshared-key', '/dev/stdin',
            'allowed-ips', f'{peer.address}/32',
            stdin=peer.psk
            )

    @staticmethod
    def wg(*args, stdin=None):
        if stdin:
            stdin = stdin.encode('utf-8')
        logging.debug('WG: %s', args)
        out = subprocess.run(
            ('wg',) + args,
            capture_output=True,
            input=stdin,
            )
        return out.stdout.decode('utf-8').strip()

    @staticmethod
    def ip(*args, stdin=None):
        if stdin:
            stdin = stdin.encode('utf-8')
        logging.debug('IP: %s', args)
        out = subprocess.run(
            ('ip',) + args,
            capture_output=True,
            input=stdin,
            )
        return out.stdout.decode('utf-8').strip()
