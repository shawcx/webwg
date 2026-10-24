
import collections
import dataclasses
import json
import logging
import os
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
        
        # a server or peer that fails here is logged and the rest still start
        for server in await _.sqlite.find(_.data.servers):
            try:
                await self.add_server(server)
            except webwg.wireguard.Error as e:
                logging.error('%s', e)

        for peer in await _.sqlite.find(_.data.peers):
            try:
                await self.add_peer(peer)
            except webwg.wireguard.Error as e:
                logging.error('%s', e)

        self.patterns = [
            ( r'/qr/(.*)',  webwg.handlers.QR         ),
            ( r'/join',     webwg.handlers.Join       ),
            ( r'/ws',       webwg.handlers.Socket, { 'websockets' : self.websockets } ),
            ( r'/([a-z]*)', _.handlers.Protected ),
            ]

        self.status_task = self.periodic(10, self.status)

    async def on_stop(self):
        for server in await _.sqlite.find(_.data.servers):
            try:
                await self.remove_server(server)
            except webwg.wireguard.Error as e:
                logging.error('%s', e)

    async def broadcast(self, msg):
        'Broadcast a message to all connected sockets'
        for ws in self.websockets.values():
            ws.write_message(msg)

    async def status(self):
        'broadcast handshake and transfer details for the peers of our interfaces'
        if not self.websockets:
            return

        status = {}
        for interface in set(self.interfaces.values()):
            try:
                peers = await webwg.wireguard.peers(interface)
            except webwg.wireguard.Error as e:
                logging.warning('%s', e)
                continue
            if peers:
                status[interface] = peers

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

    async def add_server(self, server):
        logging.info('Creating wireguard interface: %s: %s', server.interface, f'{server.network}/24')
        await webwg.wireguard.create(server.interface, server.network, server.port, server.priv, server.mtu)
        self.interfaces[server.instance] = server.interface

        # hub peers reach each other through the server, so forward packets
        # received on this interface; isolated peers only reach the server
        if server.type in ('hub', 'isolated'):
            webwg.wireguard.forwarding(server.interface, server.type == 'hub')

    async def remove_server(self, server):
        self.interfaces.pop(server.instance, None)
        logging.info('Removing wireguard interface: %s: %s', server.interface, f'{server.network}/24')
        await webwg.wireguard.delete(server.interface)

    async def add_peer(self, peer):
        interface = self.interfaces.get(peer.instance)
        if not interface:
            raise webwg.wireguard.Error(f'Server {peer.instance} has no interface, check the log for why')
        logging.info('Adding wireguard peer: %s: %s: %s', interface, peer.name, peer.address)
        await webwg.wireguard.set_peer(interface, peer.pub, peer.psk, f'{peer.address}/32')

    async def remove_peer(self, peer):
        interface = self.interfaces.get(peer.instance)
        if not interface:
            # its server never got an interface, so there is nothing to remove
            return
        logging.info('Removing wireguard peer: %s: %s: %s', interface, peer.name, peer.address)
        await webwg.wireguard.remove_peer(interface, peer.pub)
