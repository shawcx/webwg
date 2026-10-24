
import base64
import json
import logging
import os
import time

import _

import webwg


class pending:
    name      : str = _.data.pkey()
    instance  : str = _.data.refs('servers.instance')
    pub       : str
    psk       : str
    address   : str
    remote    : str
    ip        : str
    created   : int


@_.data.handles(pending)
class PendingHandler(_.records.HandlerInterface):
# comes in from the cliwg.py client
    async def post(self, pending_id):
        agent = self.request.headers.get('User-Agent', None)
        if agent != 'cliwg':
            raise _.HTTPError(500)

        try:
            request = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise _.HTTPError(500)

        try:
            name      = request['name']
            peer_pub  = request['peer_pub']
            peer_ec   = webwg.crypto.EC(request['peer_ec'])
        except:
            raise _.HTTPError(500)

        # default to the first server if one is not specified
        instance = request.get('instance')
        if instance:
            server = await _.sqlite.find_one(_.data.servers, instance)
            if not server:
                raise _.HTTPError(410)
        else:
            servers = await _.sqlite.find(_.data.servers)
            if not servers:
                raise _.HTTPError(410)
            server = servers[0]

        assigned_addresses = set()
        assigned_addresses.add(server.network)

        prefix = server.network.rsplit('.', 1)[0] + '.'
        peer_address = None

        # gather used IP addresses for approved peers
        others = await _.sqlite.find(_.data.peers)
        for other in others:
            if other.name == name:
                raise _.HTTPError(409)
            if other.address.startswith(prefix):
                assigned_addresses.add(other.address)

        # check if peer name has been pending
        # and gather potential IP addresses for pending peers
        for pending in await _.sqlite.find(_.data.pending):
#            pending = json.loads(pending)
#            pending_pub = pending_pub.decode('utf-8')[8:]
            if pending.name == name:
                if pending.address.startswith(prefix):
                    peer_address = pending.address
                await _.sqlite.delete(pending)
#                webwg.redis.delete('pending/' + pending_pub)
                await self.application.broadcast(dict(action='delete', collection='pending', id=name))
            else:
                if pending.address.startswith(prefix):
                    assigned_addresses.add(pending.address)

        if not peer_address:
            pool = [int(x.split('.',3)[-1]) for x in assigned_addresses]
            for check in range(2,255):
                if check not in pool:
                    peer_address = f"{server['network'].rsplit('.',1)[0]}.{check}"
                    break

        server_host = f"{server['host']}:{server['port']}"

        pending = _.data.pending()
        pending.name     = name
        pending.instance = server.instance
        pending.pub      = peer_pub
        pending.address  = peer_address
        pending.remote   = server_host
        pending.ip       = self.request.remote_ip
        pending.created  = int(time.time() * 1000)

        await self.application.broadcast(dict(action='add', collection='pending', data=pending._as_dict()))

        server_ec = webwg.crypto.EC()
        ecdh = server_ec.exchange(peer_ec)
        pending.psk = base64.b64encode(ecdh[:32]).decode('ascii')

        await _.sqlite.upsert(pending)

        network = server['network'].rsplit('.', 1)[0] + '.0'

        server_response = {
            'instance'       : server.instance,
            'server_host'    : server_host,
            'server_pub'     : server.pub,
            'server_ec'      : server_ec.public(),
            'server_network' : f"{network}/24",
            'peer_address'   : peer_address,
            'mtu'            : server.mtu,
        }

        self.write(server_response)

    @_.auth.protected
    async def put(self, name):
        pending = await _.sqlite.find_one(_.data.pending, name)

        server = await _.sqlite.find_one(_.data.servers, pending.instance)
        if not server:
            raise _.HTTPError(410)

        peer = _.data.peers()
        peer.name     = pending.name
        peer.instance = pending.instance
        peer.pub      = pending.pub
        peer.psk      = pending.psk
        peer.address  = pending.address
        peer.created  = pending.created

        await _.sqlite.upsert(peer)
        await _.sqlite.delete(pending)

        self.application.add_peer(peer)

        peer = peer._as_dict()
        peer['has_config'] = False
        peer.pop('psk')

        self.set_status(204)
        await self.application.broadcast(dict(action='delete', collection='pending', id=name))
        await self.application.broadcast(dict(action='add', collection='peers', data=peer))

    @_.auth.protected
    async def delete(self, name):
        if not name:
            raise _.HTTPError(500)
        count = await self._db.delete(_.data.pending, name)
        if not count:
            raise _.HTTPError(404)
        self.set_status(204)
        await self.application.broadcast(dict(action='delete', collection='pending', id=name))
