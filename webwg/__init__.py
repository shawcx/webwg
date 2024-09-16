import os
import platform

system = platform.system().lower()

root = os.path.dirname(__file__)
root = os.path.abspath(root)

# a generic error class for throwing exceptions
class error(Exception):
    def __init__(self, fmt: str, *args: tuple):
        self.message = fmt % args

    def __str__(self) -> str:
        return self.message

# place to store the asyncio loop handle
import tornado.ioloop
loop = tornado.ioloop.IOLoop.current()

from .version import __version__

from . import crypto
from . import settings
from . import wg

from .application import main
