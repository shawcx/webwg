'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')


class Peers {
    static Model = Backbone.Model.extend({
        idAttribute: 'name',
        urlRoot:     '/data/peers/',
        defaults: {
            "rx":  0,
            "tx":  0,
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

    static View = Backbone.View.extend({
        el: function() { return $('#peers-table') },

        initialize: function(options) {
            _.bindAll(this, 'Add')

            this.$tbody = this.$('tbody')

            this.listenTo(this.collection, 'add',   this.Add)
            this.listenTo(this.collection, 'reset', function(models) {
                this.$tbody.empty()
                models.each((model) => {
                    this.Add(model)
                    return
                })
            })

            return this
        },

        Add: function(model) {
            let entry = new Peers.Row({
                id: "peer_row_${ model.id }",
                model: model,
                })
            this.$tbody.append(entry.$el)
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .peer-row-name' : 'onQR',
            'click .del-row'       : 'onDelete',
        },

        initialize: function(options) {
            _.bindAll(this, 'render')

            this.template = Templates['peer-row']

            this.render()

            this.listenTo(this.model, 'change',  this.render)
            this.listenTo(this.model, 'remove',  this.remove)
            this.listenTo(this.model, 'destroy', this.remove)

            return this
        },

        mapping: {
             0: 'B',
             3: 'KB',
             6: 'MB',
             9: 'GB',
            12: 'TB',
        },

        log10: function(num) {
            let count = 0
            while(num > Math.pow(10,count)) {
                count += 3
            }
            return Math.max(0, count-3)
        },

        human: function(num, count) {
            return (num / Math.pow(10,count)).toFixed(2)
        },

        render: function() {
            let model = this.model.toJSON()

            let count = 0
            count = this.log10(model.rx)
            model.rx = this.human(model.rx, count)
            model.rs = this.mapping[count]
            count = this.log10(model.tx)
            model.tx = this.human(model.tx, count)
            model.ts = this.mapping[count]

            this.$el.html(this.template(model))
            return this
        },

        onQR: function(event) {
            let qr = new Peers.QR({pub: this.model.get('pub')})
            qr.fetch({
                success: (qr) => {
                    console.log('???', qr)
                    $('#modal-title-qr').text(this.model.id)
                    $('#qr-img').html(`<img src="${qr.get('png')}" />`)
                    $('#qr-config').text(qr.get('config'))
                    $('#qr-modal').modal('show')
                }
            })
        },

        onDelete: function (event) {
            this.model.destroy({wait: true})
            event.stopPropagation()
            return false
        },
    })

    static Instances = Backbone.View.extend({
        el: function() { return $('#peer-instance') },

        events: {
            'change' : 'onChange',
        },

        initialize: function(options) {
            _.bindAll(this, 'render')

            this.listenTo(this.collection, 'add',    this.Add)
            this.listenTo(this.collection, 'remove', this.Remove)
            this.listenTo(this.collection, 'reset',  function(models) {
                models.each((model) => {
                    this.Add(model)
                    return
                })
            })

            return this
        },

        //render: function() {
        //    return this
        //},

        Add: function(model) {
            this.$el.append($(`<option value="${model.id}">${model.id}</option>`))
        },

        Remove: function (model) {
            //console.log('Removed', model.id, model.toJSON())
        },

        onChange: function (event) {
            //console.log('Selected:', this.el.value)
        },
    })

    static ModalView = Backbone.View.extend({
        el: function() {
            return $('#peer-modal')
        },

        events: {
            'submit' : 'onSubmit',
        },

        initialize: function(options) {
            this.el.addEventListener('show.bs.modal', this.onShow)
            return this
        },

        onShow: event => {
            return
        },

        onSubmit: function(event) {
            let values = {}
            $('#peer-new :input').each(function() {
                values[this.name] = $(this).val();
            })

            console.log('------------')
            console.log(values)
            console.log('------------')

            let onSuccess = (function(model) {
                $('#peer-modal').modal('hide')
                return
            }).bind(this);

            let peer = new Peers.Model()
            peer.save(values, {
                wait: true,
                success: onSuccess
                }
            )
            event.preventDefault()
            event.stopPropagation()
            return false
        }
    })
}

module.exports = Peers
