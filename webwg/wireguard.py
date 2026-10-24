
# WireGuard keys, interfaces and peers handled in process over netlink, in
# place of running the wg and ip commands. Everything here needs
# CAP_NET_ADMIN except the keys.

import base64
import errno
import logging
import os

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization     import Encoding
from cryptography.hazmat.primitives.serialization     import NoEncryption
from cryptography.hazmat.primitives.serialization     import PrivateFormat
from cryptography.hazmat.primitives.serialization     import PublicFormat

from pyroute2 import AsyncIPRoute
from pyroute2 import AsyncWireGuard
from pyroute2.netlink.exceptions import NetlinkError

# pyroute2 logs every netlink message at debug level and WireGuard replies
# carry the private and preshared keys, so keep it quiet even with --debug
logging.getLogger('pyroute2').setLevel(logging.WARNING)


class Error(Exception):
    'a netlink request failed, the message says what was being done and why'


def _error(doing, e):
    reason = os.strerror(e.code) if isinstance(e.code, int) else str(e)
    if e.code == errno.EPERM:
        reason += ', webwg needs root or CAP_NET_ADMIN'
    return Error(f'{doing}: {reason}')


def genkey():
    'a new private key, base64 like wg genkey'
    key = X25519PrivateKey.generate()
    return base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode('ascii')


def pubkey(private):
    'the public key of a base64 private key, like wg pubkey'
    key = X25519PrivateKey.from_private_bytes(base64.b64decode(private))
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode('ascii')


def genpsk():
    'a new preshared key, like wg genpsk'
    return base64.b64encode(os.urandom(32)).decode('ascii')


class _WireGuard:
    'AsyncWireGuard has to bind to the generic netlink family before use'
    async def __aenter__(self):
        self.wg = AsyncWireGuard()
        await self.wg.setup_endpoint()
        return self.wg

    async def __aexit__(self, *args):
        self.wg.close()


async def create(interface, address, port, private, mtu):
    'create a WireGuard interface with its address, key and port, and bring it up'
    try:
        async with AsyncIPRoute() as ipr:
            try:
                await ipr.link('add', ifname=interface, kind='wireguard')
            except NetlinkError as e:
                if e.code != errno.EEXIST:
                    raise
                # left behind by a run that did not stop cleanly, start it over
                # unless the name belongs to something that is not WireGuard
                (link,) = await ipr.link('get', ifname=interface)
                if link.get(('linkinfo', 'kind')) != 'wireguard':
                    raise
                logging.warning('Replacing leftover interface: %s', interface)
                await ipr.link('del', ifname=interface)
                await ipr.link('add', ifname=interface, kind='wireguard')

            (index,) = await ipr.link_lookup(ifname=interface)
            await ipr.addr('add', index=index, address=address, prefixlen=24)

            async with _WireGuard() as wg:
                await wg.set(interface, private_key=private, listen_port=int(port))

            await ipr.link('set', index=index, mtu=int(mtu), state='up')
    except NetlinkError as e:
        raise _error(f'Creating interface {interface}', e) from None


async def delete(interface):
    'remove a WireGuard interface, one that is already gone is fine'
    try:
        async with AsyncIPRoute() as ipr:
            await ipr.link('del', ifname=interface)
    except NetlinkError as e:
        if e.code != errno.ENODEV:
            raise _error(f'Removing interface {interface}', e) from None


async def set_peer(interface, pub, psk, allowed):
    'add a peer to an interface, or update it'
    peer = {
        'public_key'    : pub,
        'preshared_key' : psk,
        'allowed_ips'   : [allowed],
        }
    try:
        async with _WireGuard() as wg:
            await wg.set(interface, peer=peer)
    except NetlinkError as e:
        raise _error(f'Adding peer to {interface}', e) from None


async def remove_peer(interface, pub):
    'remove a peer from an interface, a missing interface is fine'
    try:
        async with _WireGuard() as wg:
            await wg.set(interface, peer={'public_key': pub, 'remove': True})
    except NetlinkError as e:
        if e.code != errno.ENODEV:
            raise _error(f'Removing peer from {interface}', e) from None


def _endpoint(value):
    if not value:
        return None
    if ':' in value['addr']:
        return f"[{value['addr']}]:{value['port']}"
    return f"{value['addr']}:{value['port']}"


async def peers(interface):
    'handshake, transfer and endpoint for each peer of an interface, never any keys but the public one'
    status = []
    try:
        async with _WireGuard() as wg:
            async for msg in await wg.info(interface):
                for peer in msg.get('WGDEVICE_A_PEERS') or []:
                    pub = peer.get('WGPEER_A_PUBLIC_KEY')
                    handshake = peer.get('WGPEER_A_LAST_HANDSHAKE_TIME') or {}
                    status.append(dict(
                        pub       = pub.decode('ascii') if isinstance(pub, bytes) else pub,
                        endpoint  = _endpoint(peer.get('WGPEER_A_ENDPOINT')),
                        handshake = handshake.get('tv_sec', 0),
                        rx        = peer.get('WGPEER_A_RX_BYTES') or 0,
                        tx        = peer.get('WGPEER_A_TX_BYTES') or 0,
                        ))
    except NetlinkError as e:
        raise _error(f'Reading peers of {interface}', e) from None
    return status


def forwarding(interface, enable):
    'set IPv4 forwarding for packets received on a single interface'
    if not interface or '/' in interface or interface.startswith('.'):
        logging.warning('Invalid interface name: %s', interface)
        return
    try:
        with open(f'/proc/sys/net/ipv4/conf/{interface}/forwarding', 'w') as fp:
            fp.write('1' if enable else '0')
    except OSError as e:
        logging.warning('Unable to set forwarding on %s: %s', interface, e)
