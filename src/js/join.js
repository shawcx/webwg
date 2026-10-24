'use strict'

var qrcode = require('qrcode-generator')
var wgkeys = require('./wgkeys.js')

// the config only exists in this page, so warn before leaving until it is saved
var unsaved = false

window.addEventListener('beforeunload', function(event) {
    if (unsaved) {
        event.preventDefault()
    }
})

document.addEventListener('DOMContentLoaded', function() {
    let form = document.getElementById('join-form')
    if (!form) {
        return
    }
    if (!wgkeys.supported()) {
        fail('This page has to be opened over HTTPS to create keys. You can use cliwg.py instead.')
        document.getElementById('join-submit').disabled = true
        return
    }
    form.addEventListener('submit', function(event) {
        event.preventDefault()
        join()
    })
})

function fail(message) {
    let error = document.getElementById('join-error')
    error.textContent = message || ''
    error.hidden = !message
}

async function join() {
    let button   = document.getElementById('join-submit')
    let name     = document.getElementById('join-name').value.trim()
    let instance = document.getElementById('join-instance').value

    fail(null)
    button.disabled = true
    try {
        await request(name, instance)
    } finally {
        button.disabled = false
    }
}

async function request(name, instance) {
    let keys, exchange
    try {
        keys     = await wgkeys.keypair()
        exchange = await wgkeys.exchange()
    } catch (e) {
        fail("This browser can't create WireGuard keys. Update it, or use cliwg.py instead.")
        return
    }

    let peer = {
        'name'     : name,
        'instance' : instance,
        'peer_pub' : keys.pub,
        'peer_ec'  : exchange.pub,
    }

    let response
    try {
        response = await fetch('data/pending', {
            method:  'POST',
            headers: {
                'Content-Type'   : 'application/json; charset=utf-8',
                'X-WebWG-Client' : 'join',
            },
            body: JSON.stringify(peer),
        })
    } catch (e) {
        fail('Could not reach the server. Check the connection and try again.')
        return
    }

    if (409 === response.status) {
        fail(`A device named "${name}" already exists. Pick another name.`)
        return
    }
    if (410 === response.status) {
        fail('That server no longer exists. Reload the page and pick another.')
        return
    }
    if (!response.ok) {
        fail(`The server returned ${response.status} ${response.statusText}.`)
        return
    }

    let params = await response.json()
    params.psk      = await exchange.psk(params.server_ec)
    params.peer_key = keys.priv
    show(name, params)
}

function show(name, params) {
    let config = wgkeys.config(params)
    unsaved = true

    let qr = qrcode(0, 'L')
    qr.addData(config)
    qr.make()
    document.getElementById('join-qr').innerHTML = qr.createSvgTag({ cellSize: 4, margin: 4, scalable: true })

    document.getElementById('join-peer').textContent   = name
    document.getElementById('join-config').textContent = config

    let download = document.getElementById('join-download')
    download.href     = URL.createObjectURL(new Blob([config], { type: 'text/plain' }))
    download.download = `${params.instance}-${name}.conf`
    download.addEventListener('click', function() {
        unsaved = false
    })

    let copy = document.getElementById('join-copy')
    copy.addEventListener('click', async function() {
        try {
            await navigator.clipboard.writeText(config)
            copy.textContent = 'Copied'
            unsaved = false
        } catch (e) {
            copy.textContent = 'Copy failed'
        }
    })

    document.getElementById('join-form').hidden   = true
    document.getElementById('join-result').hidden = false
}
