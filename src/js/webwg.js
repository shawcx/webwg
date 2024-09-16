'use strict'

window.$ = window.jQuery = require('jquery')

var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

let Socket    = require('./socket.js')
let Servers   = require('./servers.js')
let Peers     = require('./peers.js')
let Pending   = require('./pending.js')
let Users     = require('./users.js')
let Sessions  = require('./sessions.js')

window.Templates = {}


$(document).ready(function() {
    $('script[type="text/template"]').each(function() {
        Templates[this.id.slice(2)] = _.template(this.text)
    })
    new WebWG()
})


class WebWG {
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

        this.dispatch = _.clone(Backbone.Events)
        this.dispatch.on('connected', this.onConnected, this)
        this.dispatch.on('status',    this.onStatus,    this)
        this.dispatch.on('add',       this.onAdd,       this)
        this.dispatch.on('update',    this.onUpdate,    this)
        this.dispatch.on('delete',    this.onDelete,    this)

        let promises = [
            this.servers.fetch({reset: true}),
            this.peers.fetch({reset: true}),
            this.pending.fetch({reset: true}),
            this.users.fetch({reset: true}),
            this.sessions.fetch({reset: true}),
        ]
        Promise.all(promises).then(() => {
            this.socket = new Socket({
                onmessage: (msg) => {
                    let action = msg.action
                    delete msg.action
                    this.dispatch.trigger(action, msg)
                }
            })
        })

    }

    onConnected() {
        console.info('Connected:', this.socket.wsurl)
        //Backbone.history.start()
    }

    onStatus(msg) {
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

    onAdd(msg) {
        let collection = this[msg.collection]
        if (!collection) {
            return
        }
        collection.add(msg.data, {merge: true})
    }

    onUpdate(msg) {
        let collection = this[msg.collection]
        if (!collection) {
            return
        }

        let key   = msg.key
        let value = msg.data[key]

        let model = collection.findWhere({[key]:value})
        if (!model) {
            return
        }

        model.set(msg.data)
    }

    onDelete(msg) {
        let collection = this[msg.collection]
        if (!collection) {
            return
        }
        collection.remove(msg.id)
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
