
import json

import tornado.web

import webwg


class Base(tornado.web.RequestHandler):
    def get_current_user(self):
        session_id = self.get_secure_cookie('id', max_age_days=1)
        if not session_id:
            return None
        session_id = session_id.decode('utf-8')

        session = webwg.redis.get('session/' + session_id)
        if not session:
            return None

        #return json.loads(session.decode('utf-8'))
        return json.loads(session)

    def initialize(self, template='index'):
        self.template = template + '.html'

    def get(self, template=None):
        template = template + '.html' if template else self.template
        self.render(template)


class Protected(Base):
    @tornado.web.authenticated
    def get(self, template=None):
        super(Protected, self).get(template)

webwg.BaseHandler = Base


from .login     import Login,Logout
from .servers   import Server
from .peers     import Peers
from .config    import Config,QR
from .pending   import Pending
from .users     import Users
from .sessions  import Sessions
from .websocket import WebSocket
