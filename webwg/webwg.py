
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

# this will change the default authentication behavior
# for all the handlers associated with the loaded components
# must be set before _.settings.load is called
_.auth.protected = _.auth.filter_user(lambda current_user: current_user)

# record handlers are open by default, require a session for them as well
_.auth.records = _.auth.filter_user(lambda current_user: current_user)

from . import handlers

class WebWg(_.WebApplication):
    async def initialize(self):
        self.websockets = {}
        self.interfaces = {}
        self.configs    = {}
        
        for server in await _.sqlite.find(_.data.servers):
            self.add_server(server)

        for peer in await _.sqlite.find(_.data.peers):
            self.add_peer(peer)

        self.patterns = [
            ( r'/qr/(.*)',  webwg.handlers.QR         ),
            ( r'/join',     webwg.handlers.Join       ),
            ( r'/ws',       webwg.handlers.Socket, { 'websockets' : self.websockets } ),
            ( r'/([a-z]*)', _.handlers.Protected ),
            ]

        self.status_task = self.periodic(10, self.status)

    async def on_stop(self):
        for server in await _.sqlite.find(_.data.servers):
            self.remove_server(server)

    async def broadcast(self, msg):
        'Broadcast a message to all connected sockets'
        for ws in self.websockets.values():
            ws.write_message(msg)

    async def status(self):
        'broadcast handshake and transfer details for the peers of our interfaces'
        if not self.websockets:
            return

        interfaces = set(self.interfaces.values())
        status = collections.defaultdict(list)
        # peer lines have 9 tab separated fields, interface lines have 5 and
        # hold the private key, the preshared key field is never sent on
        for line in self.wg('show', 'all', 'dump').splitlines():
            fields = line.split('\t')
            if len(fields) != 9 or fields[0] not in interfaces:
                continue
            interface, pub, psk, endpoint, allowed, handshake, rx, tx, keepalive = fields
            status[interface].append(dict(
                pub       = pub,
                endpoint  = None if endpoint == '(none)' else endpoint,
                handshake = int(handshake),
                rx        = int(rx),
                tx        = int(tx),
                ))

        if status:
            await self.broadcast(dict(action='status', now=int(time.time()), status=status))

    async def on_dblogin_add_user(self, name, user):
        'make adjustments to the record before calling sql statement'
        user.disabled = False
        user.isadmin  = True
        user.created  = _.now()
        data = user._as_dict()
        data.pop('password', None)
        try:
            await self.broadcast(dict(action='add', collection='users', data=data))
        except AttributeError:
            pass

    async def on_dbcache_delete(self, component, session_id):
        'allow apps to make adjustments to the record before calling sql statement'
        await self.broadcast(dict(action='delete', collection='sessions', id=session_id))

    async def on_gitlab_login_success(self, handler, user):
        if user['bot']:
            raise _.HTTPError(403)

        session = {
            'session_id' : str(uuid.uuid4()),
            'auth'       : 'GitLab',
            'username'   : user['username'],
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : _.now(),
            }
        await self.broadcast(dict(action='add', collection='sessions', data=session))
        return session

    async def on_login_success(self, handler, user):
        user.last = _.now()
        await _.sqlite.upsert(user)

        session = {
            'session_id' : str(uuid.uuid4()),
            'auth'       : 'Database',
            'username'   : user.username,
            'agent'      : handler.request.headers.get('User-Agent', ''),
            'ip'         : handler.request.remote_ip,
            'time'       : user.last,
            }
        await self.broadcast(dict(action='add', collection='sessions', data=session))
        return session

    async def on_logout(self, session_id):
        await self.broadcast(dict(action='delete', collection='sessions', id=session_id))

    async def is_session_expired(self, session, expires):
        created = session['time'] / 1000
        elapsed = (time.time() - created) / 3600
        return elapsed > expires

    def add_server(self, server):
        self.interfaces[server.instance] = server.interface
        logging.info('Creating wireguard inteface: %s: %s', server.interface, f'{server.network}/24')
        self.ip('link','add', server.interface, 'type', 'wireguard')
        self.ip('address','add', 'dev', server.interface, f'{server.network}/24')
        self.wg('set', server.interface,
            'listen-port', f'{server.port}',
            'private-key', '/dev/stdin',
            stdin=server.priv
            )
        self.ip('link','set', 'up', 'dev', server.interface)

        # hub peers reach each other through the server, so forward packets
        # received on this interface; isolated peers only reach the server
        if server.type in ('hub', 'isolated'):
            self.forwarding(server.interface, server.type == 'hub')

    def remove_server(self, server):
        interface = self.interfaces.pop(server.instance, None)
        logging.info('Removing wireguard inteface: %s: %s', server.interface, f'{server.network}/24')
        self.ip('link','delete', server.interface)

    def add_peer(self, peer):
        try:
            interface = self.interfaces[peer.instance]
        except KeyError:
            logging.error('No interface!')
            return
        logging.info('Adding wireguard peer: %s: %s: %s', interface, peer.name, f'{peer.address}')
        self.wg('set', interface,
            'peer', peer.pub,
            'preshared-key', '/dev/stdin',
            'allowed-ips', f'{peer.address}/32',
            stdin=peer.psk
            )

    def remove_peer(self, peer):
        try:
            interface = self.interfaces[peer.instance]
        except KeyError:
            logging.error('No interface!')
            return
        logging.info('Removing wireguard peer: %s: %s: %s', interface, peer.name, f'{peer.address}')
        self.wg('set', interface,
            'peer', peer.pub, 'remove'
            )

    @staticmethod
    def forwarding(interface, enable):
        'set IPv4 forwarding for packets received on a single interface'
        if not interface or '/' in interface or interface.startswith('.'):
            logging.warning('Invalid interface name: %s', interface)
            return
        try:
            with open(f'/proc/sys/net/ipv4/conf/{interface}/forwarding', 'w') as fp:
                fp.write('1' if enable else '0')
        except OSError as e:
            logging.warning('Unable to set forwarding on %s: %s', interface, e)

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
