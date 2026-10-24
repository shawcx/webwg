'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

var Socket    = require('./socket.js')
var util      = require('./util.js')
let Servers   = require('./records/servers.js')
let Peers     = require('./records/peers.js')
let Pending   = require('./records/pending.js')
var Users     = require('./records/users.js')
var Sessions  = require('./records/sessions.js')

window.Templates = {}

// lets util.hide know a dialog is still opening
document.addEventListener('show.bs.modal',  (event) => { event.target.dataset.opening = '1' })
document.addEventListener('shown.bs.modal', (event) => { delete event.target.dataset.opening })

$(document).ready(function() {
    $('script[type="text/template"]').each(function() {
        Templates[this.id.slice(2)] = _.template(this.text)
    })
    new WebWgApp()
})

// pages live in the URL hash: #servers/<instance> or #access
var Router = Backbone.Router.extend({
    routes: {
        'servers/:instance' : 'server',
        'access'            : 'access',
        '*other'            : 'home',
    },

    initialize: function(options) {
        this.app = options.app
    },

    server: function(instance) {
        if (!this.app.servers.get(instance)) {
            return this.home()
        }
        this.app.state.set({page: 'server', instance: instance})
    },

    access: function() {
        this.app.state.set({page: 'access'})
    },

    home: function() {
        let first = this.app.servers.first()
        if (first) {
            this.navigate(`servers/${encodeURIComponent(first.id)}`, {trigger: true, replace: true})
        } else {
            this.app.state.set({page: 'empty', instance: null})
        }
    },
})

// shows the page the state points at
var Pages = Backbone.View.extend({
    initialize: function(options) {
        this.app = options.app
        this.listenTo(this.app.state, 'change', this.render)
    },

    render: function() {
        let page     = this.app.state.get('page')
        let instance = this.app.state.get('instance')
        for (const name of ['server', 'empty', 'access']) {
            $(`#page-${name}`).prop('hidden', page !== name)
        }
        $('#page-error').prop('hidden', true)
        $('#nav-access').attr('aria-current', page === 'access' ? 'page' : null)
        if (page === 'access') {
            document.title = 'Users & sessions · WebWG'
        } else if (page === 'server') {
            document.title = `${instance} · WebWG`
        } else {
            document.title = 'WebWG'
        }
        window.scrollTo(0, 0)
        return this
    },
})

class WebWgApp {
    constructor() {
        this.servers  = new Servers.Collection
        this.peers    = new Peers.Collection
        this.pending  = new Pending.Collection
        this.users    = new Users.Collection
        this.sessions = new Sessions.Collection

        // which page and server are showing, the views follow it
        this.state  = new Backbone.Model({page: null, instance: null})
        this.router = new Router({app: this})

        new Pages({app: this})
        $('#page-error .btn-close').on('click', () => $('#page-error').prop('hidden', true))
        new Servers.Nav({app: this, collection: this.servers})
        new Servers.Detail({app: this, collection: this.servers})
        new Servers.ModalView({app: this, collection: this.servers})
        new Pending.View({app: this, collection: this.pending})
        new Peers.View({app: this, collection: this.peers})
        new Peers.ModalView({app: this, collection: this.peers})
        new Users.View({app: this, collection: this.users})
        new Users.ModalView({app: this, collection: this.users})
        new Sessions.View({app: this, collection: this.sessions})

        // leave a server's page once it is deleted, and the empty page once there is one
        this.servers.on('remove', (model) => {
            if (this.state.get('instance') === model.id) {
                this.router.home()
            }
        })
        this.servers.on('add', () => {
            if (this.state.get('page') === 'empty') {
                this.router.home()
            }
        })

        // relative times like "2 min ago" go stale without a redraw
        setInterval(() => this.state.trigger('tick'), 15000)

        this._events = _.clone(Backbone.Events)
        this._events.on('connected', this.on_connected, this)
        this._events.on('status',    this.on_status,    this)
        this._events.on('add',       this.on_add,       this)
        this._events.on('update',    this.on_update,    this)
        this._events.on('delete',    this.on_delete,    this)

        this.start([
            this.servers.fetch({reset: true}),
            this.peers.fetch({reset: true}),
            this.pending.fetch({reset: true}),
            this.users.fetch({reset: true}),
            this.sessions.fetch({reset: true}),
            ])
    }

    start(promises) {
        Promise.all(promises).then(() => {
            Backbone.history.start()
            this.socket = new Socket({
                onmessage: (msg) => {
                    let action = msg.action
                    delete msg.action
                    this._events.trigger(action, msg)
                }
            })
        })
    }

    on_connected() {
        console.info('Connected:', this.socket.wsurl)
    }

    on_status(msg) {
        if (msg.now) {
            util.skew = msg.now * 1000 - Date.now()
        }
        for (const wg in msg.status) {
            for (const peer of msg.status[wg]) {
                let model = this.peers.findWhere({pub:peer.pub})
                if (!model) {
                    continue
                }
                model.set({
                    rx        : peer.rx,
                    tx        : peer.tx,
                    handshake : peer.handshake,
                    endpoint  : peer.endpoint,
                    })
            }
        }
    }

    on_add(msg) {
        let collection = this[msg.collection]
        if (collection) {
            collection.add(msg.data, {merge: true})
        }
    }

    on_update(msg) {
        let collection = this[msg.collection]
        if (!collection) {
            return
        }

        let key   = msg.key || collection.model.prototype.idAttribute
        let value = msg.data[key]

        let model = collection.findWhere({[key]:value})
        if (model) {
            model.set(msg.data)
        }
    }

    on_delete(msg) {
        let collection = this[msg.collection]
        if (collection) {
            collection.remove(msg.id)
        }
    }
}
