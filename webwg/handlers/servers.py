
import base64
import json
import os

import tornado.web

import webwg


class Server(webwg.BaseHandler):
    # READ
    @tornado.web.authenticated
    async def get(self, instance=None):
        if instance:
            server = await webwg.db.findOne('servers', 'instance', instance)
            if not server:
                raise tornado.web.HTTPError(404)
            server = dict(server)
            self.write(server)
        else:
            data = []
            servers = await webwg.db.find('servers')
            for server in servers:
                server = dict(server)
                data.append(server)
            self.write({'data':data})
        self.finish()

    @tornado.web.authenticated
    async def put(self, instance=None):
        try:
            server = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        server_type = server.get('type')
        if not server_type:
            raise tornado.web.HTTPError(500)

        print('TODO: handle server type of:', server_type)

        server_key = webwg.wg.run('genkey')
        server_pub = webwg.wg.run('pubkey', stdin=server_key)

        server['pub'] = server_pub

        if server['interface'] in webwg.wg.configs:
            raise tornado.web.HTTPError(410)

        webwg.wg.ServerConfig.create(server, server_key)

        await webwg.db.insert('servers', server)
        self.set_status(204)
        self.application.Broadcast(dict(action='add', collection='servers', data=server))

    @tornado.web.authenticated
    async def delete(self, instance=None):
        if not instance:
            raise tornado.web.HTTPError(500)

        self.set_status(204)

        peers = await webwg.db.find('peers')
        for peer in peers:
            if peer['instance'] != instance:
                continue
            await webwg.db.delete('peers', peer['peer'], 'peer')
            self.application.Broadcast(dict(action='delete', collection='peers', id=peer['peer']))

        server = await webwg.db.findOne('servers', 'instance', instance)
        if not server:
            raise tornado.web.HTTPError(404)

        await webwg.db.delete('servers', instance, 'instance')
        self.application.Broadcast(dict(action='delete', collection='servers', id=instance))

        webwg.wg.configs[server['interface']].destroy()
