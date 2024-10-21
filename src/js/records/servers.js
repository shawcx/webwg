'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')


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

    static View = Backbone.View.extend({
        el: function() { return $('#servers-table') },

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
            let entry = new Servers.Row({
                id: `server_row_${ model.id }`,
                model: model,
                })
            this.$tbody.append(entry.$el)
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .del-row' : 'onDelete',
        },

        initialize: function(options) {
            _.bindAll(this, 'render')

            this.template = Templates['server-row']

            this.render()

            this.listenTo(this.model, 'change',  this.render)
            this.listenTo(this.model, 'remove',  this.remove)
            this.listenTo(this.model, 'destroy', this.remove)

            return this
        },

        render: function() {
            let model = this.model.toJSON()
            this.$el.html(this.template(model))
            if (model.id == current_user.id) {
                this.$el.addClass('table-light')
            }
            return this
        },

        onDelete: function (event) {
            this.model.destroy({wait: true})
            event.stopPropagation()
            return false
        },
    })

    static ModalView = Backbone.View.extend({
        el: function() {
            return $('#server-modal')
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
            $('#server-new :input').each(function() {
                values[this.name] = $(this).val();
            })

            let onSuccess = (function(model) {
                let modal = bootstrap.Modal.getInstance(this.el)
                modal.hide()
                return
            }).bind(this);

            let server = new Servers.Model()
            server.save(values, {
                wait: true,
                success: onSuccess
                }
            )
            event.preventDefault()
            event.stopPropagation()
            return false
        }
    })

    static process(status) {
        for(const wg in status) {
            let instance = status[wg]
            console.log(wg, instance.pub, instance.port)
            for(const peer of instance.peers) {
                for(const key in peer) {
                    let value = peer[key]
                    console.log('   ',key, value)
                }
            }
        }
    }
}


module.exports = Servers
