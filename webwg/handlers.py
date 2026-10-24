
import base64
import io
import logging
import sys

import _.websockets

try:
    import qrcode
except ImportError:
    print('[!] ERROR: qrcode module missing')
    print('      apt install python3-qrcode')
    print('      pip install qrcode')
    print('      https://github.com/lincolnloop/python-qrcode')
    sys.exit(-1)
    sys.exit(-1)



class Socket(_.websockets.Protected):
    def on_message(self, msg):
        logging.info('websocket:on_message: %s', msg)
        self.write_message(msg)


class Join(_.handlers.Handler):
    'public page where a device requests access, its keys are made in the browser'
    async def get(self):
        servers = await _.sqlite.find(_.data.servers)
        self.render('join.html', servers=[server.instance for server in servers])


class QR(_.handlers.Protected):
    @_.auth.protected
    async def get(self, pub=None):
        if not pub:
            raise _.HTTPError(404)

        # only discard the config once the QR code has been generated
        config = self.application.configs.get(pub)
        if not config:
            raise _.HTTPError(404)

        qr = qrcode.QRCode()
        qr.add_data(config)

        if _.args.debug:
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
        self.application.configs.pop(pub, None)

        await self.application.broadcast(dict(action='update', collection='peers', key='pub', data={'pub':pub,'has_config':False}))
