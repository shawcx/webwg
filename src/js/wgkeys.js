'use strict'

// WireGuard keys and the cliwg.py preshared key exchange done with WebCrypto,
// so a device's private key is made in the browser and never sent anywhere

var subtle = globalThis.crypto && globalThis.crypto.subtle

var P384 = { name: 'ECDH', namedCurve: 'P-384' }


function b64(buffer) {
    let s = ''
    for (const b of new Uint8Array(buffer)) {
        s += String.fromCharCode(b)
    }
    return btoa(s)
}

function unb64(s) {
    return Uint8Array.from(atob(s), c => c.charCodeAt(0))
}

function pem(der) {
    let body = b64(der).match(/.{1,64}/g).join('\n')
    return `-----BEGIN PUBLIC KEY-----\n${body}\n-----END PUBLIC KEY-----\n`
}

function unpem(text) {
    return unb64(text.replace(/-----[^-]+-----|\s/g, ''))
}


// WebCrypto is only available to pages served over HTTPS or from localhost
exports.supported = function() {
    return !!subtle
}

// the same as wg genkey and wg pubkey
exports.keypair = async function() {
    let pair = await subtle.generateKey({ name: 'X25519' }, true, ['deriveBits'])
    let jwk  = await subtle.exportKey('jwk', pair.privateKey)
    let priv = unb64(jwk.d.replace(/-/g, '+').replace(/_/g, '/'))
    // clamp like wg genkey, the public key is the same either way
    priv[0]  &= 248
    priv[31]  = (priv[31] & 127) | 64
    let pub  = await subtle.exportKey('raw', pair.publicKey)
    return { priv: b64(priv), pub: b64(pub) }
}

// an ephemeral P-384 key, its ECDH secret with the server's key is the preshared key
exports.exchange = async function() {
    let pair = await subtle.generateKey(P384, false, ['deriveBits'])
    let pub  = pem(await subtle.exportKey('spki', pair.publicKey))
    return {
        pub: pub,
        psk: async function(serverPem) {
            let server = await subtle.importKey('spki', unpem(serverPem), P384, false, [])
            let bits   = await subtle.deriveBits({ name: 'ECDH', public: server }, pair.privateKey, 384)
            return b64(bits.slice(0, 32))
        }
    }
}

// matches the config cliwg.py writes
exports.config = function(params) {
    return [
        '[Interface]',
        `Address = ${params.peer_address}/32`,
        `MTU = ${params.mtu}`,
        `PrivateKey = ${params.peer_key}`,
        '[Peer]',
        `AllowedIPs = ${params.server_network}`,
        `Endpoint = ${params.server_host}`,
        'PersistentKeepalive = 25',
        `PresharedKey = ${params.psk}`,
        `PublicKey = ${params.server_pub}`,
        '',
    ].join('\n')
}
