
import json
import logging
import time
import uuid

import tornado.web

import webwg


class Login(webwg.BaseHandler):
    async def _check(self, username, password):
        if password:
            password = webwg.crypto.simple_hash(username + password)

        user = await webwg.db.findOne('users', 'username', username)
        if None == user:
            return None

        if password != user.get('password'):
            return None

        timestamp = int(time.time() * 1000)
        await webwg.db.statement('UPDATE users SET last=? WHERE username=?', timestamp, username)

        return user

    async def get(self):
        redir = self.get_argument('redir', '/')
        self.render('login.html', message=None, redir=redir)

    async def post(self):
        username = self.get_argument('username')
        username = tornado.escape.xhtml_escape(username)
        password = self.get_argument('password')

        redir = self.get_argument('redir', '/')

        user = await self._check(username, password)
        if user is None:
            self.clear_cookie('id')
            self.render('login.html', message='Invalid Login', redir=redir)
            return

        if user['disabled']:
            self.clear_cookie('id')
            self.render('login.html', message='Disabled Account', redir=redir)
            return

        session_id = str(uuid.uuid4())
        session = {
            'id'       : session_id,
            'username' : username,
            'agent'    : self.request.headers.get('User-Agent', ''),
            'ip'       : self.request.remote_ip,
            'time'     : int(time.time() * 1000),
            }


        with webwg.redis.pipeline() as pipe:
            pipe.set('session/' + session_id, json.dumps(session))
            pipe.expire('session/' + session_id, 86400)
            pipe.execute()

        self.set_secure_cookie('id', session_id, expires_days=1)
        self.redirect(redir)

        self.application.Broadcast(dict(action='add', collection='sessions', data=session))


class Logout(webwg.BaseHandler):
    def get(self):
        session_id = self.get_secure_cookie('id', max_age_days=1)
        if session_id:
            session_id = session_id.decode('utf-8')
            webwg.redis.delete(session_id)
            self.application.Broadcast(dict(action='delete', collection='sessions', id=session_id))

        self.clear_cookie('id')
        self.redirect('/')
