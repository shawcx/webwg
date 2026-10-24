'use strict'

var $        = require('jquery')
var _        = require('underscore')
var Backbone = require('backbone')

var util     = require('../util.js')

var methods = {
    'Database' : 'Password',
    'GitLab'   : 'GitLab',
}


class Sessions {
    static Model = Backbone.Model.extend({
        idAttribute: 'session_id',
        urlRoot:     '/sessions/dbcache/',
    })

    static Collection = Backbone.Collection.extend({
        model: Sessions.Model,
        url:   Sessions.Model.prototype.urlRoot,
        parse: function(response) {
            return response.data
        },
    })

    static View = Backbone.View.extend({
        el: function() { return $('#sessions-card') },

        initialize: function() {
            this.rows   = []
            this.$tbody = this.$('tbody')

            this.listenTo(this.collection, 'add remove reset', this.render)

            return this
        },

        render: function() {
            let models = this.collection.sortBy((model) => -model.get('time'))
            _.invoke(this.rows, 'remove')
            this.rows = models.map((model) => new Sessions.Row({model: model}))
            this.$tbody.append(this.rows.map((row) => row.el))
            this.$('#sessions-count').text(models.length)
            return this
        },
    })

    static Row = Backbone.View.extend({
        tagName: 'tr',

        events: {
            'click .del-row' : 'onDelete',
        },

        initialize: function(options) {
            this.template = Templates['session-row']
            this.listenTo(this.model, 'change', this.render)
            this.render()
            return this
        },

        render: function() {
            let session = this.model.toJSON()
            session.agent    = session.agent || ''
            session.method   = methods[session.auth] || session.auth
            session.browser  = util.browser(session.agent)
            session.signedIn = util.short(session.time)
            session.you      = session.session_id === current_user.session_id
            this.$el.html(this.template(session))
            return this
        },

        onDelete: function(event) {
            this.$('button').prop('disabled', true)
            this.model.destroy({
                wait:  true,
                error: (model, xhr) => {
                    this.$('button').prop('disabled', false)
                    util.alert(`Could not sign out that session. ${util.failure(xhr)}`)
                },
            })
        },
    })
}

module.exports = Sessions
