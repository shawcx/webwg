'use strict'

var $         = require('jquery')
var _         = require('underscore')
var Backbone  = require('backbone')
var bootstrap = require('bootstrap')

var util      = require('../util.js')


class Users {
    static Model = Backbone.Model.extend({
        idAttribute: 'username',
        urlRoot:     '/logins/dblogin/',
    })

    static Collection = Backbone.Collection.extend({
        model: Users.Model,
        url:   Users.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data
        },
    })

    static View = Backbone.View.extend({
        el: function() { return $('#users-card') },

        initialize: function(options) {
            this.rows   = []
            this.$tbody = this.$('tbody')

            this.listenTo(this.collection, 'add remove reset', this.render)

            return this
        },

        render: function() {
            let models = this.collection.sortBy('username')
            _.invoke(this.rows, 'remove')
            this.rows = models.map((model) => new Users.Row({model: model}))
            this.$tbody.append(this.rows.map((row) => row.el))
            this.$('#users-count').text(models.length)
            return this
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .del-row' : 'onDelete',
        },

        initialize: function(options) {
            this.template = Templates['user-row']
            this.listenTo(this.model, 'change', this.render)
            this.render()
            return this
        },

        render: function() {
            let user = this.model.toJSON()
            user.isadmin  = !!user.isadmin
            user.disabled = !!user.disabled
            user.created  = util.short(user.created)
            user.last     = user.last ? util.short(user.last) : 'Never'
            user.you      = user.username === current_user.username
            this.$el.html(this.template(user))
            return this
        },

        onDelete: function(event) {
            let username = this.model.id
            util.confirm(
                `Delete ${username}?`,
                `${username} can no longer sign in to WebWG. Sessions they already have stay open until they expire or you sign them out.`,
                'Delete user',
                () => this.model.destroy({
                    wait:  true,
                    error: (model, xhr) => util.alert(`Could not delete ${username}. ${util.failure(xhr)}`),
                }),
                )
        },
    })

    static ModalView = Backbone.View.extend({
        el: function() { return $('#user-modal') },

        events: {
            'submit' : 'onSubmit',
        },

        initialize: function(options) {
            this.form = this.$('form')[0]
            this.el.addEventListener('show.bs.modal', this.onShow.bind(this))
            return this
        },

        onShow: function(event) {
            this.form.reset()
            util.error(this.$('#user-error')[0], null)
        },

        onSubmit: function(event) {
            event.preventDefault()
            event.stopPropagation()

            let error = this.$('#user-error')[0]
            if (!this.form.checkValidity()) {
                this.form.reportValidity()
                return false
            }

            let username = this.$('#user-name').val().trim()
            let password = this.$('#user-password').val()
            if (password !== this.$('#user-confirm').val()) {
                util.error(error, "The passwords don't match.")
                return false
            }
            if (this.collection.get(username)) {
                util.error(error, `A user named "${username}" already exists.`)
                return false
            }

            let user = new Users.Model
            user.save({username: username, password: password}, {
                wait: true,
                success: () => {
                    util.hide(this.el)
                },
                error: (model, xhr) => {
                    util.error(error, util.failure(xhr))
                },
            })
            return false
        }
    })
}

module.exports = Users
