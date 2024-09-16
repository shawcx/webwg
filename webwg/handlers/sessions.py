
import base64
import json

import redis
import tornado.web

import webwg


class Sessions(webwg.BaseHandler):
    @tornado.web.authenticated
    async def get(self, session_id=None):
        if session_id:
            session = webwg.redis.get('session/' + session_id)
            if not session:
                raise tornado.web.HTTPError(404)
            session = json.loads(session)
            session['id'] = session_id
            self.write(session)
        else:
            data = []
            session_ids = webwg.redis.keys('session/*')
            for session_id in session_ids:
                session = webwg.redis.get(session_id)
                session = json.loads(session)
                #session['id'] = session_id.decode('utf-8')[8:]
                data.append(session)
            data.sort(key=lambda d: d['time'])
            self.write({'data':data})
        self.finish()

    @tornado.web.authenticated
    def post(self):
        try:
            status = json.loads(self.request.body)
        except json.decoder.JSONDecodeError:
            raise tornado.web.HTTPError(500)

        self.set_status(204)
        self.application.Broadcast(dict(action='server', status=status))

    @tornado.web.authenticated
    def delete(self, session_id=None):
        self.set_status(204)
        if session_id:
            self.application.Broadcast(dict(action='delete', collection='sessions', id=session_id))

            webwg.redis.delete('session/' + session_id)
            ws = self.application.websockets.get(session_id, None)
            if ws:
                ws.close(4004)
