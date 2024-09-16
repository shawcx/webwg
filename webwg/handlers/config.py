
import base64
import io
import json
import logging

import tornado.web
import qrcode

import webwg


class Config(webwg.BaseHandler):
    async def get(self, peer=None):
        if not peer:
            raise tornado.web.HTTPError(404)

        peer = await webwg.db.findOne('peers', 'peer', peer)
        if not peer:
            raise tornado.web.HTTPError(404)

        config = webwg.redis.get('config/'+peer['pub'])
        if not config:
            raise tornado.web.HTTPError(404)
        config = config.decode('utf-8')

        self.write(config)

        webwg.redis.delete('config/'+peer['pub'])
        self.application.Broadcast(
            dict(
                action     = 'update',
                collection = 'peers',
                key        = 'pub',
                data       = { 'pub' : peer['pub'], 'has_config' : False }
                )
            )


class QR(webwg.BaseHandler):
    @tornado.web.authenticated
    async def get(self, pub=None):
        if not pub:
            raise tornado.web.HTTPError(404)

        config = webwg.redis.get('config/'+pub)
        if not config:
            raise tornado.web.HTTPError(404)

        config = config.decode('utf-8')

        qr = qrcode.QRCode()
        qr.add_data(config)

        if webwg.args.debug:
            print()
            print(config)
            print()
            qr.print_ascii()

        img = qr.make_image()
        buffer = io.BytesIO()
        img.save(buffer, format='png')

        buffer = base64.b64encode(buffer.getvalue()).decode('ascii')
        buffer = 'data:image/png;base64,' + buffer
        self.write({'png':buffer,'config':config})

        webwg.redis.delete('config/'+pub)

        self.application.Broadcast(dict(action='update', collection='peers', key='pub', data={'pub':pub,'has_config':False}))
