'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')


class Users {
    static Model = Backbone.Model.extend({
        idAttribute: 'username',
        urlRoot:     '/data/users/',
    })

    static Collection = Backbone.Collection.extend({
        model: Users.Model,
        url:   Users.Model.prototype.urlRoot,

        parse: function(response) {
            return response.data;
        },
    })

    static View = Backbone.View.extend({
        el: function() { return $('#users-table') },

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
            let entry = new Users.Row({
                id: "user_row_${ model.id }",
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

            this.template = Templates['user-row']

            this.render()

            this.listenTo(this.model, 'change',  this.render)
            this.listenTo(this.model, 'remove',  this.remove)
            this.listenTo(this.model, 'destroy', this.remove)

            return this
        },

        render: function() {
            let model = this.model.toJSON()
            if (model.last) {
                model.last = new Date(model.last).short()
            } else {
                model.last = ''
            }
            this.$el.html(this.template(model))
            if (model.username == current_user.username) {
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

    static ModalView = Backbone.View.extend({
        el: function() { return $('#user-modal') },

        events: {
            'submit' : 'onSubmit',
        },

        initialize: function(options) {
            this.el.addEventListener('show.bs.modal', this.onShow)
            return this
        },

        onShow: function(event) {
            return
        },

        onSubmit: function(event) {
            let values = {}
            $('#user-new :input').each(function() {
                values[this.name] = $(this).val();
            })

            let user = new Users.Model
            user.save(values, {
                wait: true,
                success: () => {
                    $(this.el).modal('hide')
                    return
                }
            })
            event.preventDefault()
            event.stopPropagation()
            return false
        }
    })
}


module.exports = Users

