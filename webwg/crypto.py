
import sys

try:
    from cryptography.hazmat.primitives.asymmetric    import ec
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.hazmat.primitives.serialization import NoEncryption
    from cryptography.hazmat.primitives.serialization import PrivateFormat
    from cryptography.hazmat.primitives.serialization import PublicFormat
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
except ImportError:
    print('[!] ERROR: cryptography module missing')
    print('      apt install python3-cryptography')
    print('      pip install cryptography')
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
            if pem.startswith(b'-----BEGIN PUBLIC KEY-----'):
                self._key = load_pem_public_key(pem)
            elif pem.startswith(b'-----BEGIN PRIVATE KEY-----'):
                self._key = load_pem_private_key(pem, passwd)
            else:
                raise ValueError('Invalid PEM format')

    def public(self):
        return self._key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode('ascii')

    def private(self):
        return self._key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode('ascii')

    def exchange(self, peer):
        return self._key.exchange(ec.ECDH(), peer._key)

