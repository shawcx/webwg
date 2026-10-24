'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

var util      = require('../util.js')
var Peers     = require('./peers.js')


var types = {
    hub: {
        label : 'Hub',
        icon  : 'fa-arrows-left-right',
        note  : 'Peers can reach each other through this server',
    },
    isolated: {
        label : 'Isolated',
        icon  : 'fa-arrow-right-to-line',
        note  : 'Peers can reach this server only, not each other',
    },
    proxy: {
        label : 'Proxy',
        icon  : 'fa-globe',
        note  : 'Routes peers out to the internet',
    },
}


class Servers {
    static Model = Backbone.Model.extend({
        idAttribute: 'instance',
        urlRoot:     '/data/servers/',
    })

    static Collection = Backbone.Collection.extend({
        model: Servers.Model,
        url:   Servers.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data;
        },
    })

    // the server list in the sidebar
    static Nav = Backbone.View.extend({
        el: function() { return $('#server-nav') },

        initialize: function(options) {
            this.app      = options.app
            this.template = Templates['server-nav']

            this.listenTo(this.collection,  'add remove reset change', this.render)
            this.listenTo(this.app.pending, 'add remove reset',        this.render)
            this.listenTo(this.app.state,   'change',                  this.render)

            return this
        },

        render: function() {
            let state   = this.app.state
            let current = state.get('page') === 'server' ? state.get('instance') : null
            let items   = this.collection.map((model) => {
                let server = model.toJSON()
                server.subnet  = util.subnet(server.network)
                server.current = server.instance === current
                server.waiting = this.app.pending.where({instance: server.instance}).length
                return `<li>${this.template(server)}</li>`
            })
            this.$el.html(items.join(''))
            return this
        },
    })

    // the heading and details at the top of a server's page
    static Detail = Backbone.View.extend({
        el: function() { return $('#server-detail') },

        events: {
            'click .del-server' : 'onDelete',
            'click .copy-key'   : 'onCopy',
        },

        initialize: function(options) {
            this.app      = options.app
            this.template = Templates['server-detail']

            this.listenTo(this.app.state,  'change:instance', this.render)
            this.listenTo(this.collection, 'change',          this.render)
            this.listenTo(this.app.peers,  'add remove reset change:instance change:handshake', this.summary)
            this.listenTo(this.app.state,  'tick',            this.summary)

            return this
        },

        server: function() {
            return this.collection.get(this.app.state.get('instance'))
        },

        render: function() {
            let model = this.server()
            if (!model) {
                this.$el.empty()
                return this
            }
            let server = model.toJSON()
            _.extend(server, types[server.type] || {label: server.type, icon: 'fa-server', note: ''})
            server.typeLabel = server.label
            server.subnet    = util.subnet(server.network)
            this.$el.html(this.template(server))
            $('.server-name').text(server.instance)
            this.summary()
            return this
        },

        // peer counts change often, so only this line is redrawn for them
        summary: function() {
            let model = this.server()
            if (!model) {
                return
            }
            let peers = this.app.peers.where({instance: model.id})
            let known = peers.filter((peer) => peer.has('handshake'))
            let text  = String(peers.length)
            if (known.length) {
                let online = peers.filter((peer) => Peers.present(peer.toJSON()).status === 'online')
                text = `${online.length} of ${peers.length} online`
            }
            this.$('.peer-summary').text(text)
        },

        onCopy: async function(event) {
            let button = event.currentTarget
            util.flash(button, await util.copy(this.server().get('pub')))
        },

        onDelete: function(event) {
            let model    = this.server()
            let instance = model.id
            let peers    = this.app.peers.where({instance: instance}).length
            let waiting  = this.app.pending.where({instance: instance}).length
            util.confirm(
                `Delete ${instance}?`,
                `This removes the ${model.get('interface')} interface, its ${peers} peers and ${waiting} waiting requests. Devices using it lose access right away.`,
                'Delete server',
                () => model.destroy({
                    wait:  true,
                    error: (model, xhr) => util.alert(`Could not delete ${instance}. ${util.failure(xhr)}`),
                }),
                )
        },
    })

    static ModalView = Backbone.View.extend({
        el: function() { return $('#server-modal') },

        events: {
            'submit' : 'onSubmit',
        },

        initialize: function(options) {
            this.app  = options.app
            this.form = this.$('form')[0]
            this.el.addEventListener('show.bs.modal', this.onShow.bind(this))
            return this
        },

        // suggest an interface, port and network no other server uses
        onShow: function(event) {
            let servers = this.collection.toJSON()
            let used    = (key) => new Set(servers.map((server) => String(server[key])))

            let interfaces = used('interface')
            let iface = 0
            while (interfaces.has(`wg${iface}`)) {
                iface += 1
            }

            let ports = used('port')
            let port = 51820
            while (ports.has(String(port))) {
                port += 1
            }

            let prefixes = new Set(servers.map((server) => util.prefix(server.network)))
            let second = 8
            while (prefixes.has(`10.${second}.0`)) {
                second += 1
            }

            this.form.reset()
            this.form.interface.value = `wg${iface}`
            this.form.port.value      = port
            this.form.network.value   = `10.${second}.0.1`
            this.form.host.value      = location.hostname
            util.error(this.$('#server-error')[0], null)
        },

        onSubmit: function(event) {
            event.preventDefault()
            event.stopPropagation()

            let error = this.$('#server-error')[0]
            if (!this.form.checkValidity()) {
                this.form.reportValidity()
                return false
            }

            let values = {
                type      : this.form.querySelector('input[name="type"]:checked').value,
                instance  : this.form.instance.value.trim(),
                interface : this.form.interface.value.trim(),
                host      : this.form.host.value.trim(),
                port      : parseInt(this.form.port.value, 10),
                network   : this.form.network.value.trim(),
                mtu       : parseInt(this.form.mtu.value, 10),
            }

            // saving an existing name would replace that server
            if (this.collection.get(values.instance)) {
                util.error(error, `A server named "${values.instance}" already exists.`)
                return false
            }

            let server = new Servers.Model()
            server.save(values, {
                wait: true,
                success: (model) => {
                    this.collection.add(model.toJSON(), {merge: true})
                    util.hide(this.el)
                    this.app.router.navigate(`servers/${encodeURIComponent(values.instance)}`, {trigger: true})
                },
                error: (model, xhr) => {
                    util.error(error, util.failure(xhr))
                },
            })
            return false
        },
    })
}


module.exports = Servers
