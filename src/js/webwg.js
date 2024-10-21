'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

var Socket    = require('./socket.js')
let Servers   = require('./records/servers.js')
let Peers     = require('./records/peers.js')
let Pending   = require('./records/pending.js')
var Users     = require('./records/users.js')
var Sessions  = require('./records/sessions.js')

window.Templates = {}

$(document).ready(function() {
    $('script[type="text/template"]').each(function() {
        Templates[this.id.slice(2)] = _.template(this.text)
    })
    new WebWgApp()
})

class WebWgApp {
    constructor() {
        this.servers  = new Servers.Collection
        this.peers    = new Peers.Collection
        this.pending  = new Pending.Collection
        this.users    = new Users.Collection
        this.sessions = new Sessions.Collection

        new Servers.View({
            collection: this.servers,
            })
        new Servers.ModalView()

        new Peers.View({
            collection: this.peers,
            })
        new Peers.Instances({
            collection: this.servers,
            })
        new Peers.ModalView()

        new Pending.View({
            collection: this.pending,
            })

        new Users.View({
            collection: this.users,
            })
        new Users.ModalView()

        new Sessions.View({
            collection: this.sessions,
            })

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
        for (const wg in msg.status) {
            for (const peer of msg.status[wg]) {
                let model = this.peers.findWhere({pub:peer.pub})
                if (!model) {
                    //console.warn('Ignore:', peer.pub)
                    continue
                }
                model.set({rx:peer.rx, tx:peer.tx})
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

        let key   = collection.model.prototype.idAttribute
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


Date.prototype.short = function() {
    let month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    let h = this.getHours()
    if(h < 10) h = '0' + h
    let d = this.getDate()
    if(d < 10) d = '0' + d
    let m = this.getMinutes()
    if(m < 10) m = '0' + m
    return `${month[this.getMonth()]} ${d} ${h}:${m}`
}

//module.exports = App
