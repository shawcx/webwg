'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')


class Sessions {
    constructor() {
    }

    static Model = Backbone.Model.extend({
        idAttribute: 'id',
        urlRoot:     '/data/sessions/',
    })

    static Collection = Backbone.Collection.extend({
        model: Sessions.Model,
        url:   Sessions.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data;
        },
    })

    static View = Backbone.View.extend({
        el: function() { return $('#sessions-table') },

        initialize: function() {
            _.bindAll(this, 'Add')

            this.$tbody = this.$('tbody')

            this.listenTo(this.collection, 'add',   this.Add)
            this.listenTo(this.collection, 'reset', function(models) {
                this.$tbody.empty()
                models.forEach((model) => {
                    this.Add(model)
                }, this)
            })

            return this
        },

        Add: function(model) {
            let entry = new Sessions.Row({
                id: `session_row_${ model.id }`,
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
            this.template = Templates['session-row']

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
                this.$el.addClass('table-light webwg-hilite')
            }
            return this
        },

        onDelete: function (event) {
            this.model.destroy({wait: true})
            event.stopPropagation()
            return false
        },
    })
}


module.exports = Sessions

