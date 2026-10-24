'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')

var util     = require('../util.js')


class Pending {
    static Model = Backbone.Model.extend({
        idAttribute: 'name',
        urlRoot:     '/data/pending/',
    })

    static Collection = Backbone.Collection.extend({
        model: Pending.Model,
        url:   Pending.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data;
        },
    })

    // requests waiting for approval on the current server
    static View = Backbone.View.extend({
        el: function() { return $('#pending-card') },

        initialize: function(options) {
            this.app   = options.app
            this.rows  = []
            this.$list = this.$('#pending-list')

            this.listenTo(this.collection, 'add remove reset', this.render)
            this.listenTo(this.app.state,  'change:instance',  this.render)
            this.listenTo(this.app.state,  'tick',             this.tick)

            return this
        },

        render: function() {
            let instance = this.app.state.get('instance')
            let models   = _.sortBy(this.collection.where({instance: instance}), (model) => model.get('created'))

            _.invoke(this.rows, 'remove')
            this.rows = models.map((model) => new Pending.Row({model: model}))
            this.$list.append(this.rows.map((row) => row.el))

            let count = this.$('#pending-count')
            count.text(models.length)
            count.toggleClass('wg-count-warn', !!models.length)
            this.$list.prop('hidden', !models.length)
            this.$('#pending-empty').prop('hidden', !!models.length)
            this.$('#pending-command').text(`python3 cliwg.py ${location.origin} <name> -i ${instance}`)
            return this
        },

        tick: function() {
            _.invoke(this.rows, 'render')
        },
    })

    static Row = Backbone.View.extend({
        tagName:   'li',
        className: 'wg-req',

        events: {
            'click .approve-req' : 'onApprove',
            'click .reject-req'  : 'onReject',
        },

        initialize: function(options) {
            this.template = Templates['req-row']
            this.listenTo(this.model, 'change', this.render)
            this.render()
            return this
        },

        render: function() {
            let request = this.model.toJSON()
            request.when = util.ago(request.created)
            let html = this.template(request)
            if (html !== this.html) {
                this.$el.html(html)
                this.html = html
            }
            return this
        },

        onApprove: function(event) {
            this.$('button').prop('disabled', true)
            this.model.save(null, {
                wait:  true,
                error: () => this.$('button').prop('disabled', false),
            })
        },

        onReject: function(event) {
            this.$('button').prop('disabled', true)
            this.model.destroy({
                wait:  true,
                error: () => this.$('button').prop('disabled', false),
            })
        },
    })
}


module.exports = Pending
