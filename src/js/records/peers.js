'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

var util      = require('../util.js')

// a peer that shook hands within this many seconds counts as online
var ONLINE = 180


class Peers {
    static Model = Backbone.Model.extend({
        idAttribute: 'name',
        urlRoot:     '/data/peers/',
        defaults: {
            "rx":  0,
            "tx":  0,
            "has_config" : false,
        }
    })

    static Collection = Backbone.Collection.extend({
        model: Peers.Model,
        url:   Peers.Model.prototype.urlRoot,

        parse: function(response) {
            return response.data;
        },
    })

    static QR = Backbone.Model.extend({
        idAttribute: 'pub',
        urlRoot:     '/qr/',
    })

    // status and labels for a peer row, handshake is unset until the server reports it
    static present(peer) {
        if (peer.handshake === undefined) {
            peer.status         = 'unknown'
            peer.statusLabel    = 'Unknown'
            peer.handshakeLabel = '—'
            peer.rxLabel        = '—'
            peer.txLabel        = '—'
        } else {
            let age = util.now() / 1000 - peer.handshake
            if (!peer.handshake) {
                peer.status      = 'fresh'
                peer.statusLabel = 'No handshake yet'
            } else if (age < ONLINE) {
                peer.status      = 'online'
                peer.statusLabel = 'Online'
            } else {
                peer.status      = 'idle'
                peer.statusLabel = 'Idle'
            }
            peer.handshakeLabel = peer.handshake ? util.ago(peer.handshake * 1000) : 'Never'
            peer.rxLabel        = util.bytes(peer.rx)
            peer.txLabel        = util.bytes(peer.tx)
        }
        peer.endpoint = peer.endpoint || ''
        peer.added    = util.short(peer.created)
        return peer
    }

    // a peer's one time config, the server forgets it once fetched
    static showConfig(model) {
        let qr = new Peers.QR({pub: model.get('pub')})
        qr.fetch({
            success: (qr) => Peers.config(model.toJSON(), qr.get('png'), qr.get('config')),
            error:   () => model.set('has_config', false),
        })
    }

    static config(peer, png, config) {
        let el       = document.getElementById('config-modal')
        let download = document.getElementById('config-download')
        let copy     = document.getElementById('config-copy')

        $('#config-name').text(peer.name)
        $('#config-meta').text(`${peer.instance} · ${peer.address}`)
        $('#config-qr').attr({src: png, alt: `QR code of the ${peer.name} config`})
        $('#config-text').text(config)

        let url = URL.createObjectURL(new Blob([config], {type: 'text/plain'}))
        download.href     = url
        download.download = `${peer.instance}-${peer.name}.conf`
        $('#config-download-label').text(`Download ${download.download}`)

        copy.onclick = async () => util.flash(copy, await util.copy(config))

        // drop the private key from the page once the dialog closes
        el.addEventListener('hidden.bs.modal', () => {
            URL.revokeObjectURL(url)
            download.removeAttribute('href')
            $('#config-text').text('')
            $('#config-qr').attr({src: '', alt: ''})
        }, {once: true})

        bootstrap.Modal.getOrCreateInstance(el).show()
    }

    // the peers table, only the current server's peers
    static View = Backbone.View.extend({
        el: function() { return $('#peers-card') },

        initialize: function(options) {
            this.app    = options.app
            this.rows   = []
            this.$tbody = this.$('tbody')

            this.listenTo(this.collection, 'add remove reset change:instance', this.render)
            this.listenTo(this.app.state,  'change:instance', this.render)
            this.listenTo(this.app.state,  'tick',            this.tick)

            return this
        },

        render: function() {
            let instance = this.app.state.get('instance')
            let models   = this.collection.where({instance: instance})
            models = _.sortBy(models, (model) => util.octets(model.get('address')))

            _.invoke(this.rows, 'remove')
            this.rows = models.map((model) => new Peers.Row({model: model}))
            this.$tbody.append(this.rows.map((row) => row.el))

            this.$('#peers-count').text(models.length)
            this.$('#peers-wrap').prop('hidden', !models.length)
            this.$('#peers-empty').prop('hidden', !!models.length)
            return this
        },

        tick: function() {
            _.invoke(this.rows, 'render')
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .show-config' : 'onConfig',
            'click .del-row'     : 'onDelete',
        },

        initialize: function(options) {
            this.template = Templates['peer-row']
            this.listenTo(this.model, 'change', this.render)
            this.render()
            return this
        },

        render: function() {
            let html = this.template(Peers.present(this.model.toJSON()))
            // status arrives every few seconds, only redraw on a real change so focus survives
            if (html !== this.html) {
                this.$el.html(html)
                this.html = html
            }
            return this
        },

        onConfig: function(event) {
            Peers.showConfig(this.model)
        },

        onDelete: function(event) {
            let name = this.model.id
            util.confirm(
                `Remove ${name}?`,
                `${name} loses access to ${this.model.get('instance')} right away. Bringing it back takes a new config.`,
                'Remove peer',
                () => this.model.destroy({wait: true}),
                )
        },
    })

    static ModalView = Backbone.View.extend({
        el: function() { return $('#peer-modal') },

        events: {
            'submit'                : 'onSubmit',
            'change #peer-instance' : 'suggest',
        },

        initialize: function(options) {
            this.app  = options.app
            this.form = this.$('form')[0]
            this.el.addEventListener('show.bs.modal', this.onShow.bind(this))
            return this
        },

        onShow: function(event) {
            this.form.reset()
            let select = this.$('#peer-instance').empty()
            this.app.servers.each((server) => {
                select.append($('<option>').val(server.id).text(`${server.id} · ${server.get('type')} · ${util.subnet(server.get('network'))}`))
            })
            select.val(this.app.state.get('instance') || select.find('option').first().val())
            this.suggest()
            util.error(this.$('#peer-error')[0], null)
        },

        // the next address no peer or request on that server has
        suggest: function() {
            let server = this.app.servers.get(this.form.instance.value)
            if (!server) {
                return
            }
            let taken = new Set()
            for (const record of this.app.peers.where({instance: server.id}).concat(this.app.pending.where({instance: server.id}))) {
                taken.add(record.get('address'))
            }
            this.form.address.value = util.nextAddress(server.get('network'), taken)
            this.$('#peer-address-hint').text(`Next free address on ${server.id}.`)
        },

        onSubmit: function(event) {
            event.preventDefault()
            event.stopPropagation()

            let error = this.$('#peer-error')[0]
            if (!this.form.checkValidity()) {
                this.form.reportValidity()
                return false
            }

            let values = {
                name     : this.form.elements['name'].value.trim(),
                instance : this.form.instance.value,
                address  : this.form.address.value.trim(),
            }

            if (this.collection.get(values.name) || this.app.pending.get(values.name)) {
                util.error(error, `A peer named "${values.name}" already exists.`)
                return false
            }

            let peer = new Peers.Model()
            peer.save(values, {
                wait: true,
                success: (model) => {
                    this.collection.add(model.toJSON(), {merge: true})
                    util.hide(this.el)
                    Peers.showConfig(this.collection.get(values.name))
                },
                error: (model, xhr) => {
                    util.error(error, util.failure(xhr, `A peer named "${values.name}" already exists.`))
                },
            })
            return false
        },
    })
}

module.exports = Peers
