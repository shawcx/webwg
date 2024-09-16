
import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric         import ec
from cryptography.hazmat.primitives.ciphers            import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes      import CBC
from cryptography.hazmat.primitives.hashes             import SHA256
from cryptography.hazmat.primitives.serialization      import Encoding
from cryptography.hazmat.primitives.serialization      import NoEncryption
from cryptography.hazmat.primitives.serialization      import PrivateFormat
from cryptography.hazmat.primitives.serialization      import PublicFormat
from cryptography.hazmat.primitives.serialization      import load_pem_private_key
from cryptography.hazmat.primitives.serialization      import load_pem_public_key


class AES:
    @staticmethod
    def encrypt(msg, key, iv):
        cipher = Cipher(AES(key), CBC(iv)).encryptor()
        return cipher.update(msg) + cipher.finalize()

    @staticmethod
    def decrypt(msg, key, iv):
        cipher = Cipher(AES(key), CBC(iv)).decryptor()
        return cipher.update(msg) + cipher.finalize()


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


def simple_hash(value):
    value = value.encode('utf-8')
    for i in range(99999):
        value = hashlib.sha512(value).digest()
    return base64.b64encode(value).decode('ascii')
