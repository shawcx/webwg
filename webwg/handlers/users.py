
import json
import time

import tornado.web

import webwg


class Users(webwg.BaseHandler):
    # READ
    @tornado.web.authenticated
    async def get(self, username=None):
        if username:
            user = await webwg.db.findOne('users', 'username', username)
            user.pop('password', None)
            self.write(user)
        else:
            users = await webwg.db.find('users')
            data = []
            for user in users:
                user = dict(user)
                user.pop('password', None)
                data.append(user)
            self.write({'data':data})
        self.finish()

    @tornado.web.authenticated
    async def put(self, username=None):
        try:
            user = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        username = user.get('username')
        password = user.get('password')
        if not username or not password:
            raise tornado.web.HTTPError(500)

        if password != user.get('confirm'):
            raise tornado.web.HTTPError(500)

        password = webwg.crypto.simple_hash(username + password)
        creation = int(time.time() * 1000)

        user = {
            'username' : username,
            'password' : password,
            'disabled' : 0,
            'created'  : creation,
            'last'     : None,
        }
        await webwg.db.insert('users', user)

        self.application.Broadcast(dict(action='add', collection='users', data=user))

        self.set_status(204)
        self.finish()

    @tornado.web.authenticated
    async def delete(self, username=None):
        self.set_status(204)

        await webwg.db.delete('users', username, 'username')
        self.application.Broadcast(dict(action='delete', collection='users', id=username))

        session_ids = webwg.redis.keys('session/*')
        for session_id in session_ids:
            session = webwg.redis.get(session_id)
            session = json.loads(session)
            if session['username'] == username:
                webwg.redis.delete(session_id)
                self.application.Broadcast(dict(action='delete', collection='sessions', id=session['id']))
