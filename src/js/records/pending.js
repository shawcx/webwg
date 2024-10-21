'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')


class Pending {
    constructor() {
    }

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

    static View = Backbone.View.extend({
        el: function() { return $('#pending-table') },

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
            let entry = new Pending.Row({
                id: `req_row_${ model.id }`,
                model: model,
                })
            this.$tbody.append(entry.$el)
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .approve-req' : 'onApprove',
            'click .del-row'     : 'onDelete',
        },

        initialize: function(options) {
            _.bindAll(this, 'render')

            this.template = Templates['req-row']

            this.render()

            this.listenTo(this.model, 'change',  this.render)
            this.listenTo(this.model, 'remove',  this.remove)
            this.listenTo(this.model, 'destroy', this.remove)

            return this
        },

        render: function() {
            let model = this.model.toJSON()
            this.$el.html(this.template(model))
            return this
        },

        onApprove: function(event) {
            this.model.save(null, {wait:true})
            event.stopPropagation()
            return false
        },

        onDelete: function (event) {
            this.model.destroy({wait: true})
            event.stopPropagation()
            return false
        },
    })
}


module.exports = Pending

