
import base64
import io
import json
import logging
import time

import tornado.web

import webwg


class Peers(webwg.BaseHandler):
    template = '\n'.join((
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

    # READ
    @tornado.web.authenticated
    async def get(self, peer=None):
        if peer:
            peer = await webwg.db.findOne('peers', 'peer', peer)
            if not peer:
                raise tornado.web.HTTPError(404)
            self.write(peer)
        else:
            peers = await webwg.db.find('peers')
            data = []
            for peer in peers:
                peer = dict(peer)
                peer['has_config'] = webwg.redis.exists('config/'+peer['pub'])
                data.append(peer)
            self.write({'data':data})

        self.finish()

    @tornado.web.authenticated
    async def put(self, _peer=None):
        try:
            peer = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        peer.pop('rx', None)
        peer.pop('tx', None)

        server = await webwg.db.findOne('servers', 'instance', peer['instance'])
        if not server:
            raise tornado.web.HTTPError(404)

        # TODO: check addresses
        #prefix   = server['network'].rsplit('.', 1)[0] + '.'

        peer_key = webwg.wg.run('genkey')
        peer_pub = webwg.wg.run('pubkey', stdin=peer_key)
        psk      = webwg.wg.run('genpsk')

        peer['pub']    = peer_pub
        peer['remote'] = f"{server['host']}:{server['port']}"
        peer['created'] = int(time.time() * 1000)

        try:
            await webwg.db.insert('peers', peer)
        except webwg.error as e:
            logging.warning('Name conflict: %s', peer['peer'])
            raise tornado.web.HTTPError(409)

        config = Peers.template.format(
            peer_address   = peer['address'],
            mtu            = server['mtu'],
            peer_key       = peer_key,
            server_network = server['network'],
            server_host    = peer['remote'],
            psk            = psk,
            server_pub     = server['pub'],
            )

        with webwg.redis.pipeline() as pipe:
            pipe.set('config/' + peer_pub, config)
            pipe.expire('config/' + peer_pub, 86400)
            pipe.execute()

        peer['has_config'] = True

        self.set_status(204)
        self.application.Broadcast(dict(action='add', collection='peers', data=peer))

        serverConfig = webwg.wg.configs[server['interface']]
        serverConfig.addPeer(pub=peer_pub, psk=psk, address=peer['address'])

    @tornado.web.authenticated
    async def delete(self, _peer=None):
        if not _peer:
            raise tornado.web.HTTPError(500)

        peer = await webwg.db.findOne('peers', 'peer', _peer)
        if not peer:
            raise tornado.web.HTTPError(404)

        server = await webwg.db.findOne('servers', 'instance', peer['instance'])
        if not server:
            raise tornado.web.HTTPError(404)

        await webwg.db.delete('peers', _peer, 'peer')
        self.application.Broadcast(dict(action='delete', collection='peers', id=_peer))

        serverConfig = webwg.wg.configs[server['interface']]

        try:
            serverConfig.removePeer(peer)
        except KeyError:
            raise tornado.web.HTTPError(404)

        self.set_status(204)
