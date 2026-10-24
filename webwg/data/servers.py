
import logging
import os

import _

import webwg


class servers:
    instance  : str = _.data.pkey()
    type      : str
    pub       : str
    priv      : str
    interface : str
    host      : str
    port      : int
    network   : str
    mtu       : int


@_.data.handles(servers)
class ServersHandler(_.records.HandlerInterface):
    @_.auth.protected
    async def get(self, instance):
        if not instance:
            servers = await self._db.find(_.data.servers)
            data = []
            for server in servers:
                server = server._as_dict()
                server.pop('priv')
                data.append(server)
            self.write(dict(data=data))
        else:
            server = await self._db.find_one(_.data.servers, instance)
            if server is None:
                raise _.HTTPError(404)
            server = server._as_dict()
            server.pop('priv')
            self.write(server)

    @_.auth.protected
    async def put(self, instance):
        server_type = self.data.get('type')
        if not server_type:
            raise _.HTTPError(500)

        server = await _.sqlite.find_one(_.data.servers, self.data.get('instance'))
        existing = server is not None

        try:
            if existing:
                # the interface comes back below with the new settings and its peers
                await self.application.remove_server(server)
                server(**self.data)
            else:
                server = _.data.servers._from_dict(self.data)
                server.priv = webwg.wireguard.genkey()
                server.pub  = webwg.wireguard.pubkey(server.priv)

            await self.application.add_server(server)
            if existing:
                for peer in await _.sqlite.find(_.data.peers, server.instance, 'instance'):
                    await self.application.add_peer(peer)
        except webwg.wireguard.Error as e:
            logging.error('%s', e)
            self.set_status(500)
            self.write(dict(error=str(e)))
            return

        await _.sqlite.upsert(server)

        server = server._as_dict()
        server.pop('priv')

        self.write(server)
        await self.application.broadcast(dict(action='add', collection='servers', data=server))

    @_.auth.protected
    async def delete(self, instance):
        if instance is None:
            raise _.HTTPError(500)
        server = await _.sqlite.find_one(_.data.servers, instance)
        if not server:
            raise _.HTTPError(404)

        peers = await _.sqlite.find(_.data.peers, server.instance, 'instance')
        pending = await _.sqlite.find(_.data.pending, server.instance, 'instance')

        try:
            await self.application.remove_server(server)
        except webwg.wireguard.Error as e:
            logging.error('%s', e)
            self.set_status(500)
            self.write(dict(error=str(e)))
            return

        await _.sqlite.delete(server)
    
        self.set_status(204)
        for peer in peers:
            await self.application.broadcast(dict(action='delete', collection='peers', id=peer.name))
        for queue in pending:
            await self.application.broadcast(dict(action='delete', collection='pending', id=queue.name))
        await self.application.broadcast(dict(action='delete', collection='servers', id=server.instance))
