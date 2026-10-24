'use strict'

var bootstrap = require('bootstrap')

// milliseconds between the server's clock and ours, from status messages
exports.skew = 0

exports.now = function() {
    return Date.now() + exports.skew
}

var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

exports.short = function(ms) {
    if (!ms) {
        return '—'
    }
    let date = new Date(ms)
    let pad  = (n) => String(n).padStart(2, '0')
    return `${months[date.getMonth()]} ${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

exports.ago = function(ms) {
    let seconds = Math.max(0, Math.round((exports.now() - ms) / 1000))
    if (seconds < 60) {
        return `${seconds} s ago`
    }
    let minutes = Math.round(seconds / 60)
    if (minutes < 60) {
        return `${minutes} min ago`
    }
    let hours = Math.round(minutes / 60)
    if (hours < 24) {
        return `${hours} h ago`
    }
    let days = Math.round(hours / 24)
    if (days < 14) {
        return `${days} d ago`
    }
    return exports.short(ms)
}

var units = ['B', 'KB', 'MB', 'GB', 'TB']

exports.bytes = function(n) {
    let unit = 0
    while (n >= 1000 && unit < units.length - 1) {
        n /= 1000
        unit += 1
    }
    if (unit) {
        n = n.toFixed(n < 10 ? 2 : n < 100 ? 1 : 0)
    }
    return `${n} ${units[unit]}`
}

// servers are always a /24, network holds the server's own address
exports.prefix = function(address) {
    return String(address).split('.').slice(0, 3).join('.')
}

exports.subnet = function(address) {
    return exports.prefix(address) + '.0/24'
}

exports.octets = function(address) {
    return String(address).split('.').reduce((n, part) => n * 256 + (parseInt(part, 10) || 0), 0)
}

exports.nextAddress = function(network, taken) {
    let prefix = exports.prefix(network)
    for (let host = 2; host < 255; host++) {
        let address = `${prefix}.${host}`
        if (address !== network && !taken.has(address)) {
            return address
        }
    }
    return ''
}

exports.browser = function(agent) {
    if (!agent) {
        return 'Unknown'
    }
    let name = /Edg\//.test(agent)     ? 'Edge'
             : /Firefox\//.test(agent) ? 'Firefox'
             : /Chrome\//.test(agent)  ? 'Chrome'
             : /Safari\//.test(agent)  ? 'Safari'
             : agent.split(/[\/ ]/)[0]
    let os = /Android/.test(agent)     ? 'Android'
           : /iPhone|iPad/.test(agent) ? 'iOS'
           : /Windows/.test(agent)     ? 'Windows'
           : /Mac OS X/.test(agent)    ? 'macOS'
           : /Linux/.test(agent)       ? 'Linux'
           : ''
    return os ? `${name} on ${os}` : name
}

exports.copy = async function(text) {
    try {
        await navigator.clipboard.writeText(text)
        return true
    } catch (e) {
    }
    // the clipboard API needs HTTPS, fall back for plain HTTP
    let area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity  = '0'
    document.body.appendChild(area)
    area.select()
    let ok = false
    try {
        ok = document.execCommand('copy')
    } catch (e) {
    }
    area.remove()
    return ok
}

// briefly show on a copy button whether it worked
exports.flash = function(button, ok) {
    let icon  = button.querySelector('i')
    let label = button.querySelector('.label')
    let saved = [icon && icon.className, label && label.textContent]
    if (icon) {
        icon.className = `fa-regular ${ok ? 'fa-check' : 'fa-xmark'}`
    }
    if (label) {
        label.textContent = ok ? 'Copied' : 'Copy failed'
    }
    clearTimeout(button._flash)
    button._flash = setTimeout(() => {
        if (icon) {
            icon.className = saved[0]
        }
        if (label) {
            label.textContent = saved[1]
        }
    }, 1500)
}

// bootstrap ignores hide() while a dialog is still opening, so wait for it
exports.hide = function(el) {
    let modal = bootstrap.Modal.getOrCreateInstance(el)
    if (el.dataset.opening) {
        el.addEventListener('shown.bs.modal', () => modal.hide(), {once: true})
    } else {
        modal.hide()
    }
}

exports.confirm = function(title, body, label, action) {
    let el = document.getElementById('confirm-modal')
    document.getElementById('confirm-title').textContent = title
    document.getElementById('confirm-body').textContent  = body
    let ok = document.getElementById('confirm-ok')
    ok.textContent = label
    let modal = bootstrap.Modal.getOrCreateInstance(el)
    ok.onclick = function() {
        modal.hide()
        action()
    }
    modal.show()
}

// show a failed action at the top of the page, for actions without a dialog of their own
exports.alert = function(message) {
    let el = document.getElementById('page-error')
    el.querySelector('.message').textContent = message
    el.hidden = false
    window.scrollTo(0, 0)
}

// fill a form's error box from a failed request, or hide it
exports.error = function(el, message) {
    el.textContent = message || ''
    el.hidden = !message
}

exports.failure = function(xhr, conflict) {
    if (xhr && 409 === xhr.status && conflict) {
        return conflict
    }
    // the server explains failures it can describe, such as a netlink error
    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
        return xhr.responseJSON.error
    }
    if (xhr && xhr.status) {
        return `The server returned ${xhr.status} ${xhr.statusText}.`
    }
    return 'Could not reach the server.'
}
