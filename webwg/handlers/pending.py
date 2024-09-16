
import base64
import json
import logging
import os
import time
import uuid

import tornado.web

import webwg


class Pending(webwg.BaseHandler):
    # READ
    @tornado.web.authenticated
    async def get(self, pending_pub=None):
        if pending_pub:
            pending = webwg.redis.get('pending/' + pending_pub)
            if not pending:
                raise tornado.web.HTTPError(404)
            pending = json.loads(pending)
            pending['id'] = pending_pub
            self.write(pending)
        else:
            data = []
            pending_pubs = webwg.redis.keys('pending/*')
            for pending_pub in pending_pubs:
                pending = webwg.redis.get(pending_pub)
                pending = json.loads(pending)
                pending['id'] = pending_pub.decode('utf-8')[8:]
                data.append(pending)
            data.sort(key=lambda d: d['created'])
            self.write({'data':data})
        self.finish()

# comes in from the cliwg.py client
    async def post(self):
        agent = self.request.headers.get('User-Agent', None)
        if agent != 'cliwg':
            raise tornado.web.HTTPError(500)

        try:
            request = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        try:
            peer      = request['peer']
            peer_pub  = request['peer_pub']
            peer_ec   = webwg.crypto.EC(request['peer_ec'])
        except:
            raise tornado.web.HTTPError(500)

        # default to the first server if one is not specified
        instance = request.get('instance')
        if instance:
            server = await webwg.db.findOne('servers', 'instance', instance)
            if not server:
                raise tornado.web.HTTPError(410)
        else:
            servers = await webwg.db.find('servers')
            if not servers:
                raise tornado.web.HTTPError(410)
            server = dict(servers[0])

        instance = server['instance']
        network  = server['network']
        prefix   = network.rsplit('.', 1)[0] + '.'

        assigned_addresses = set()
        assigned_addresses.add(network)

        peer_address = None

        # gather used IP addresses for approved peers
        others = await webwg.db.find('peers')
        for other in others:
            if other['peer'] == peer:
                raise tornado.web.HTTPError(409)
            if other['address'].startswith(prefix):
                assigned_addresses.add(other['address'])

        # check if peer name has been pending
        # and gather potential IP addresses for pending peers
        pending_pubs = webwg.redis.keys('pending/*')
        for pending_pub in pending_pubs:
            pending = webwg.redis.get(pending_pub)
            pending = json.loads(pending)
            pending_pub = pending_pub.decode('utf-8')[8:]

            if peer == pending['peer']:
                if pending['address'].startswith(prefix):
                    peer_address = pending['address']
                webwg.redis.delete('pending/' + pending_pub)
                self.application.Broadcast(dict(action='delete', collection='pending', id=pending_pub))
            else:
                if pending['address'].startswith(prefix):
                    assigned_addresses.add(pending['address'])

        if not peer_address:
            pool = [int(x.split('.',3)[-1]) for x in assigned_addresses]
            for check in range(2,255):
                if check not in pool:
                    peer_address = f"{server['network'].rsplit('.',1)[0]}.{check}"
                    break

        server_ec = webwg.crypto.EC()
        ecdh = server_ec.exchange(peer_ec)
        psk = base64.b64encode(ecdh[:32]).decode('ascii')

        server_host = f"{server['host']}:{server['port']}"

        pending = {
            'peer'      : peer,
            'pub'       : peer_pub,
            'instance'  : instance,
            'address'   : peer_address,
            'remote'    : server_host,
            'ip'        : self.request.remote_ip,
            'created'   : int(time.time() * 1000),
            }

        self.application.Broadcast(dict(action='add', collection='pending', data=pending))

        pending['psk'] = psk

        with webwg.redis.pipeline() as pipe:
            pipe.set('pending/' + peer_pub, json.dumps(pending))
            pipe.expire('pending/' + peer_pub, 86400)
            pipe.execute()

        network = server['network'].rsplit('.', 1)[0] + '.0'

        server_response = {
            'server_host'    : server_host,
            'server_pub'     : server['pub'],
            'server_ec'      : server_ec.public(),
            'server_network' : f"{network}/24",
            'peer_address'   : peer_address,
            'mtu'            : server['mtu'],
        }

        self.write(server_response)

    @tornado.web.authenticated
    async def put(self, peer_pub=None):
        pending = webwg.redis.get('pending/' + peer_pub)
        try:
            pending = json.loads(pending)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        try:
            instance = pending.get('instance')
        except KeyError:
            raise tornado.web.HTTPError(500)

        server = await webwg.db.findOne('servers', 'instance', instance)
        if not server:
            raise tornado.web.HTTPError(410)

        pending.pop('id', None)
        pending.pop('ip', None)

        serverConfig = webwg.wg.configs[server['interface']]
        serverConfig.addPeer(**pending)

        pending.pop('psk')

        await webwg.db.insert('peers', pending, 'peer')
        webwg.redis.delete('pending/' + peer_pub)

        pending['has_config'] = False

        self.set_status(204)
        self.application.Broadcast(dict(action='delete', collection='pending', id=peer_pub))
        self.application.Broadcast(dict(action='add', collection='peers', data=pending))

    @tornado.web.authenticated
    def delete(self, peer_pub=None):
        self.set_status(204)
        if peer_pub:
            webwg.redis.delete('pending/' + peer_pub)
            self.application.Broadcast(dict(action='delete', collection='pending', id=peer_pub))
