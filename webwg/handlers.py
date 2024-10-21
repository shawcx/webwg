
import base64
import json
import logging
import os
import time
import uuid

import _.websockets

import webwg


class Socket(_.websockets.Protected):
    def on_message(self, msg):
        logging.info('websocket:on_message: %s', msg)
        self.write_message(msg)

