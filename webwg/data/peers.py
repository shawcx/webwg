
import logging
import os

import _

import webwg


class peers:
    name      : str = _.data.pkey()
    instance  : str = _.data.refs('servers.instance')
    pub       : str
    psk       : str
    address   : str
    created   : int

@_.data.handles(peers)
class PeersHandler(_.records.HandlerInterface):
    @_.auth.protected
    async def delete(self, name):
        if name is None:
            raise _.HTTPError(500)
        peer = await _.sqlite.find_one(_.data.peers, name)
        if not peer:
            raise _.HTTPError(404)

        server = await _.sqlite.find_one(_.data.servers, peer.instance)

        self.application.wg('set', server.interface,
            'peer', peer.pub, 'remove'
            )

        await _.sqlite.delete(peer)
        
        await self.application.broadcast(dict(action='delete', collection='peers', id=name))
        self.set_status(204)
