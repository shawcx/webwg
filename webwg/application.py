
import argparse
import asyncio
import binascii
import json
import logging
import os
import signal
import socket
import sys

import redis
import tornado.ioloop
import tornado.web
import tornado.websocket

import webwg

from . import handlers
from . import database


def main():
    webwg.settings.parse()

    db = database.Sync()
    db.open()
    if webwg.args.init:
        db.initialize()
        sys.exit(0)
    if webwg.args.user:
        db.user(*webwg.args.user)
        sys.exit(0)
    if webwg.args.list_users:
        db.list_users()
        sys.exit(0)
    db.close()

    try:
        Application()
    except webwg.error as e:
        logging.error('%s', e)
        sys.exit(-1)


class Application(tornado.web.Application):
    def __init__(self):
        self.websockets = {}

        logging.info('Connecting to database')
        webwg.db = database.Async()

        logging.info('Loading server configs')
        webwg.wg.ServerConfig.loadAll()

        webwg.loop.run_sync(webwg.db.connect)

        webwg.redis = redis.StrictRedis(db=9)
        webwg.redis.ping()
        cookie_secret = webwg.redis.get('cookie_secret')
        if cookie_secret is None:
            cookie_secret = binascii.b2a_base64(os.urandom(32))
            webwg.redis.set('cookie_secret', cookie_secret)

        # Tornado settings
        settings = dict(
            static_path   = os.path.join(webwg.root, 'static'),
            template_path = os.path.join(webwg.root, 'templates'),
            cookie_secret = cookie_secret,
            login_url     = '/login',
            debug         = webwg.args.debug,
            )

        patterns = [
            ( r'/data/servers/(.*)',  handlers.Server   ),
            ( r'/data/peers/(.*)',    handlers.Peers    ),
            ( r'/data/pending/(.*)',  handlers.Pending  ),
            ( r'/data/users/(.*)',    handlers.Users    ),
            ( r'/data/sessions/(.*)', handlers.Sessions ),

            ( r'/request',       handlers.Pending    ),
            ( r'/config/(.*)',   handlers.Config     ),
            ( r'/qr/(.*)',       handlers.QR         ),

            ( r'/login',         handlers.Login      ),
            ( r'/logout',        handlers.Logout     ),

            ( r'/ws',            handlers.WebSocket  ),
            ( r'/',              handlers.Protected  ),

            ( r'/(favicon.ico)', tornado.web.StaticFileHandler, {'path':''}),
            ]

        super(Application, self).__init__(patterns, **settings)

        try:
            self.listen(webwg.args.port, webwg.args.addr, xheaders=True)
        except Exception as e:
            raise

        logging.info('Listening on %s:%d', webwg.args.addr, webwg.args.port)

        self.status_cb = tornado.ioloop.PeriodicCallback(self.Status, 1000)
        self.status_cb.start()

        signal.signal(signal.SIGINT,  self.SignalHandler)
        signal.signal(signal.SIGTERM, self.SignalHandler)

        webwg.loop.start()
        logging.info('Good-Bye')

    def Status(self):
        stats = webwg.wg.status()
        if stats is None:
            self.status_cb.stop()
        self.Broadcast(dict(action='status', status=stats))

    def Stop(self):
        for ws in self.websockets.values():
            ws.close(4004)
        # hack: stop the ioloop at the end of the db close
        webwg.loop.add_callback(webwg.db.close)

    def SignalHandler(self, signum: int, frame):
        if signal.SIGINT == signum:
            print()
        logging.info('Terminating')
        webwg.loop.add_callback_from_signal(self.Stop)

    def Broadcast(self, msg):
        'Broadcast a message to all connected sockets'
        for ws in self.websockets.values():
            ws.write_message(msg)
