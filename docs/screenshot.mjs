// Signs in to the demo that screenshot.sh stages and captures the home
// server's page, by driving headless Chrome over the DevTools protocol.
//
//   node screenshot.mjs <base url> <output.png>

import fs from 'node:fs'

const [,, base, out] = process.argv
const WIDTH = 1360

const version = await (await fetch('http://127.0.0.1:9222/json/version')).json()
const ws = new WebSocket(version.webSocketDebuggerUrl)
await new Promise((resolve) => ws.onopen = resolve)

let id = 0
const waiting = new Map()
const errors = []
ws.onmessage = (message) => {
    const msg = JSON.parse(message.data)
    if (waiting.has(msg.id)) {
        waiting.get(msg.id)(msg)
        waiting.delete(msg.id)
    } else if (msg.method === 'Runtime.exceptionThrown') {
        errors.push(msg.params.exceptionDetails.text)
    }
}

const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const i = ++id
    waiting.set(i, (msg) => msg.error ? reject(new Error(`${method}: ${msg.error.message}`)) : resolve(msg.result))
    ws.send(JSON.stringify({ id: i, method, params, sessionId }))
})

const { targetId } = await send('Target.createTarget', { url: 'about:blank' })
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
const page = (method, params) => send(method, params, sessionId)

const evaluate = async (expression) => {
    const result = await page('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    return result.result.value
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const until = async (expression, ms = 30000) => {
    for (let t = 0; t < ms; t += 100) {
        if (await evaluate(expression)) {
            return
        }
        await sleep(100)
    }
    throw new Error(`timed out waiting for ${expression}`)
}
// twice the pixels so it stays sharp on high density screens
const size = (height) => page('Emulation.setDeviceMetricsOverride', { width: WIDTH, height, deviceScaleFactor: 2, mobile: false })

await page('Runtime.enable')
await size(860)

await page('Page.navigate', { url: `${base}/login` })
await until(`document.readyState === 'complete' && !!document.getElementById('login-user')`)
await evaluate(`
    document.getElementById('login-user').value = 'admin'
    document.getElementById('login-pass').value = 'demo'
    document.querySelector('form.wg-panel').submit()
`)
await until(`location.hash === '#servers/home' && !!document.querySelector('#peers-card tbody tr')`)

// the first status broadcast fills in the handshakes and traffic
await until(`[...document.querySelectorAll('#peers-card tbody tr')].filter((row) => row.textContent.includes('Online')).length === 3`)
await evaluate(`document.activeElement && document.activeElement.blur()`)
await sleep(800)

await size(await evaluate(`Math.max(860, document.documentElement.scrollHeight)`))
await sleep(300)
const { data } = await page('Page.captureScreenshot', { format: 'png' })
fs.writeFileSync(out, Buffer.from(data, 'base64'))

if (errors.length) {
    console.error('page errors:', errors.join(' | '))
    process.exit(1)
}
console.log(`wrote ${out}`)
process.exit(0)
