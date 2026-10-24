
import json
import logging
import time

import _

import webwg


class peers:
    name      : str = _.data.pkey()
    instance  : str = _.data.refs('servers.instance')
    pub       : str
    psk       : str
    remote    : str
    address   : str
    created   : int


_template = '\n'.join((
    '[Interface]',
    'Address = {peer_address}/32',
    'MTU = {mtu}',
    'PrivateKey = {peer_key}',
    '[Peer]',
    'AllowedIPs = {server_network}',
    'Endpoint = {server_host}',
    'PersistentKeepalive = 25',
    'PresharedKey = {psk}',
    'PublicKey = {server_pub}',
    ))


@_.data.handles(peers)
class PeersHandler(_.records.HandlerInterface):
    @_.auth.protected
    async def put(self, _peer=None):
        try:
            request = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise _.HTTPError(500)

        request.pop('rx', None)
        request.pop('tx', None)

        peer = _.data.peers()
        peer(**request)

        server = await _.sqlite.find_one(_.data.servers, peer.instance)
        if not server:
            raise _.HTTPError(404)

        # TODO: check addresses
        #prefix   = server['network'].rsplit('.', 1)[0] + '.'

        if await _.sqlite.find_one(_.data.peers, peer.name):
            logging.warning('Name conflict: %s', peer.name)
            raise _.HTTPError(409)

        peer_key = webwg.wireguard.genkey()
        peer.pub = webwg.wireguard.pubkey(peer_key)
        peer.psk = webwg.wireguard.genpsk()

        peer.remote  = f"{server.host}:{server.port}"
        peer.created = int(time.time() * 1000)

        try:
            await self.application.add_peer(peer)
        except webwg.wireguard.Error as e:
            logging.error('%s', e)
            self.set_status(500)
            self.write(dict(error=str(e)))
            return

        try:
            await _.sqlite.upsert(peer)
        except _.error as e:
            logging.warning('Name conflict: %s', peer.name)
            await self.application.remove_peer(peer)
            raise _.HTTPError(409)

        network = server.network.rsplit('.', 1)[0] + '.0'

        self.application.configs[peer.pub] = _template.format(
            peer_address   = peer.address,
            mtu            = server.mtu,
            peer_key       = peer_key,
            server_network = f'{network}/24',
            server_host    = peer.remote,
            psk            = peer.psk,
            server_pub     = server.pub,
            )

        peer = peer._as_dict()
        peer.pop('psk')
        peer['has_config'] = True

        # the creator needs the public key to fetch the config right away
        self.write(peer)
        await self.application.broadcast(dict(action='add', collection='peers', data=peer))

    @_.auth.protected
    async def delete(self, name):
        if name is None:
            raise _.HTTPError(500)
        peer = await _.sqlite.find_one(_.data.peers, name)
        if not peer:
            raise _.HTTPError(404)

        try:
            await self.application.remove_peer(peer)
        except webwg.wireguard.Error as e:
            logging.error('%s', e)
            self.set_status(500)
            self.write(dict(error=str(e)))
            return

        await _.sqlite.delete(peer)

        self.set_status(204)
        await self.application.broadcast(dict(action='delete', collection='peers', id=name))
