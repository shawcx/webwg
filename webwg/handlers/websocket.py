
import sys
import os
import json
import logging
import uuid

import tornado.ioloop
import tornado.web
import tornado.websocket

import webwg


SESSION_EXPIRE = 3600 * 8


class WebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        self.session_id = self.get_secure_cookie('id', max_age_days=1)
        self.session_id = self.session_id.decode('utf-8')

        if not self.session_id:
            self.close(4004)
            return

        self.session = webwg.redis.get('session/' + self.session_id)
        if not self.session:
            self.close(4004)
            return

        self.application.websockets[self.session_id] = self
        self.write_message(dict(action='connected'))

    def on_message(self, msg):
        logging.debug('WebSocket: %s', msg)
        if msg == 'ping':
            return

        for ws in self.application.websockets.values():
            if ws is self:
                continue
            ws.write_message(msg)

    def on_close(self):
        try:
            del self.application.websockets[self.session_id]
        except KeyError:
            pass
