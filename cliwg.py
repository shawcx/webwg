#!/usr/bin/env python3

import sys
import os
import argparse
import base64
import collections
import json
import subprocess
import textwrap
import urllib.parse
import urllib.request

try:
    import qrcode
except:
    qrcode = None


argparser = argparse.ArgumentParser()

argparser.add_argument('server',
    metavar='server',
    help='webwg server'
    )

argparser.add_argument('peer',
    metavar='peer',
    help='webwg peer'
    )

argparser.add_argument('-i', '--instance',
    metavar='<instance>',
    help='webwg instance'
    )

argparser.add_argument('--qr',
    action='store_true',
    help='output QR code'
    )


def main():
    args = argparser.parse_args()

    print('[+] Name:', args.peer)

    def _wg(*args, stdin=None):
        if stdin:
            stdin = stdin.encode('utf-8')
        out = subprocess.run(
            ('wg',) + args,
            capture_output=True,
            input=stdin,
            )
        return out.stdout.decode('utf-8').strip()

    peer_ec = EC()

    peer_key = _wg('genkey')
    peer_pub = _wg('pubkey', stdin=peer_key)
    print('[+] Pub: ', peer_pub)

    peer = {
        'name'     : args.peer,
        'instance' : args.instance,
        'peer_pub' : peer_pub,
        'peer_ec'  : peer_ec.public(),
        }
    peer = json.dumps(peer).encode('utf-8')

    headers = {
        'User-Agent': 'cliwg',
    }

    if not args.server.startswith(('http://','https://')):
        args.server = 'https://' + args.server

    url = urllib.parse.urlparse(args.server)
    if not url.path:
        url = url._replace(path='/data/pending')
    url = urllib.parse.urlunparse(url)

    print('[+] URL: ', url)
    request = urllib.request.Request(url, data=peer, headers=headers)
    request.add_header('Content-Type', 'application/json; charset=utf-8')
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        if 410 == e.code:
            if args.instance:
                print('[!] ERROR: no instance', repr(args.instance), 'on server')
            else:
                print('[!] ERROR: no instance on server')
            return -1
        elif 409 == e.code:
            print('[!] ERROR: peer', repr(args.peer), 'already exists')
            return -1
        else:
            raise
    except Exception as e:
        print('[-] Could not connect:', e)
        return -1

    if response.getcode() != 200:
        print('[-] Returned:', response.getcode())
        return -1

    params = json.loads(response.read(response.length))

    server_ec = params['server_ec']
    server_ec = EC(server_ec)
    psk = peer_ec.exchange(server_ec)
    psk = base64.b64encode(psk[:32]).decode('ascii')

    params['psk']      = psk
    params['peer_key'] = peer_key

    template = '''
[Interface]
Address = {peer_address}/32
MTU = {mtu}
PrivateKey = {peer_key}
[Peer]
AllowedIPs = {server_network}
Endpoint = {server_host}
PersistentKeepalive = 25
PresharedKey = {psk}
PublicKey = {server_pub}
'''

    config = template[1:].format(**params)

    if args.qr:
        if qrcode:
            qr = qrcode.QRCode()
            qr.add_data(config)
            qr.print_ascii()
        else:
            print('[!] ERROR: qrcode package missing')
            print('      apt install python3-qrcode')
            print('      https://github.com/lincolnloop/python-qrcode')

    with open(f'{params["instance"]}-{args.peer}.conf', 'w') as fp:
        fp.write(config)

    return 0


try:
    from cryptography.hazmat.primitives.asymmetric         import ec
    from cryptography.hazmat.primitives.serialization      import Encoding
    from cryptography.hazmat.primitives.serialization      import NoEncryption
    from cryptography.hazmat.primitives.serialization      import PrivateFormat
    from cryptography.hazmat.primitives.serialization      import PublicFormat
    from cryptography.hazmat.primitives.serialization      import load_pem_private_key
    from cryptography.hazmat.primitives.serialization      import load_pem_public_key
except ImportError:
    print('[!] ERROR: cryptography module missing')
    print('      apt install python3-cryptography')
    print('      https://cryptography.io')
    sys.exit(-1)


class EC:
    def __init__(self, pem=None, passwd=None):
        if not pem:
            self._key = ec.generate_private_key(ec.SECP384R1())
        else:
            if isinstance(pem, str):
                pem = pem.encode('ascii')
            if not isinstance(pem, bytes):
                raise ValueError('Invalid PEM type')
            if b'PUBLIC' in pem:
                self._key = load_pem_public_key(pem)
            elif b'PRIVATE' in pem:
                self._key = load_pem_private_key(pem, passwd)
            else:
                raise ValueError('Invalid PEM format')

    def public(self):
        return self._key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode('ascii')

    def private(self):
        return self._key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode('ascii')

    def exchange(self, peer):
        return self._key.exchange(ec.ECDH(), peer._key)


if '__main__' == __name__:
    sys.exit(main())
