"""wrapper around PyCrypto cryptography library

Information sources:
    - http://eli.thegreenplace.net/2010/06/25/aes-encryption-of-files-in-python-with-pycrypto/
    - http://code.activestate.com/recipes/576980-authenticated-encryption-with-pycrypto/

"""
import base64
import hashlib
import hmac
import logging
import os

try:
    from Crypto.Cipher import AES
    AES_BLOCK_SIZE = AES.block_size
except ImportError:  # pragma: no cover
    logging.getLogger(__name__).error('auxlib.crypt is a pycrypto wrapper, '
                                      'which is not installed in the current '
                                      'environment.')  # pragma: no cover

from .compat import text_type
from .exceptions import AuthenticationError

log = logging.getLogger(__name__)

__all__ = ["as_base64", "from_base64", "encrypt", "decrypt", "aes_encrypt", "aes_decrypt"]

AES_KEY_SIZE = 32   # 32 byte key size ==> AES-256
HMAC_SIG_SIZE = hashlib.sha256().digest_size


def encrypt(secret_key, data):
    message_encryption_key = generate_encryption_key()
    encrypted_data = aes_encrypt(message_encryption_key, data)
    hashed_secret = generate_hash_from_secret(secret_key)
    encryption_key_encrypted = aes_encrypt(hashed_secret, message_encryption_key)
    return encryption_key_encrypted, encrypted_data


def decrypt(secret_key, encryption_key_encrypted, encrypted_data):
    hashed_secret = generate_hash_from_secret(secret_key)
    message_encryption_key = aes_decrypt(hashed_secret, encryption_key_encrypted)
    data = aes_decrypt(message_encryption_key, encrypted_data)
    return data


def as_base64(content):
    if isinstance(content, text_type):
        content = content.encode("UTF-8")
    return base64.urlsafe_b64encode(content)


def from_base64(content):
    if isinstance(content, text_type):
        content = content.encode('UTF-8')
    return base64.urlsafe_b64decode(content)


def generate_encryption_key():
    """Create a new, random encryption key for use by this module.

    The encryption key is composed of an AES key and an HMAC signing key.

    Returns:
        str: base64-encoded encryption key

    """
    return as_base64(os.urandom(AES_KEY_SIZE + HMAC_SIG_SIZE))


def generate_hash_from_secret(secret):
    return as_base64(hashlib.sha512(text_type(secret).encode('UTF-8')).digest())


def aes_encrypt(base64_encryption_key, data):
    """Encrypt data with AES-CBC and sign it with HMAC-SHA256

    Arguments:
        base64_encryption_key (str): a base64-encoded string containing an AES encryption key
            and HMAC signing key as generated by generate_encryption_key()
        data (str): a byte string containing the data to be encrypted

    Returns:
        str: the encrypted data as a byte string with the HMAC signature appended to the end

    """
    if isinstance(data, text_type):
        data = data.encode("UTF-8")
    aes_key_bytes, hmac_key_bytes = _extract_keys(base64_encryption_key)
    data = _pad(data)
    iv_bytes = os.urandom(AES_BLOCK_SIZE)
    cipher = AES.new(aes_key_bytes, mode=AES.MODE_CBC, IV=iv_bytes)
    data = iv_bytes + cipher.encrypt(data)  # prepend init vector
    hmac_signature = hmac.new(hmac_key_bytes, data, hashlib.sha256).digest()
    return as_base64(data + hmac_signature)


def aes_decrypt(base64_encryption_key, base64_data):
    """Verify HMAC-SHA256 signature and decrypt data with AES-CBC

    Arguments:
        encryption_key (str): a base64-encoded string containing an AES encryption key and HMAC
            signing key as generated by generate_encryption_key()
        data (str): a byte string containing the data decrypted with an HMAC signing key
            appended to the end

    Returns:
        str: a byte string containing the data that was originally encrypted

    Raises:
        AuthenticationError: when the HMAC-SHA256 signature authentication fails

    """
    data = from_base64(base64_data)
    aes_key_bytes, hmac_key_bytes = _extract_keys(base64_encryption_key)
    data, hmac_signature = data[:-HMAC_SIG_SIZE], data[-HMAC_SIG_SIZE:]
    if hmac.new(hmac_key_bytes, data, hashlib.sha256).digest() != hmac_signature:
        raise AuthenticationError("HMAC authentication failed")
    iv_bytes, data = data[:AES_BLOCK_SIZE], data[AES_BLOCK_SIZE:]
    cipher = AES.new(aes_key_bytes, AES.MODE_CBC, iv_bytes)
    data = cipher.decrypt(data)
    return _unpad(data)


def _pad(s):
    padding_bytes = AES_BLOCK_SIZE - len(s) % AES_BLOCK_SIZE
    return s + (chr(padding_bytes) * padding_bytes).encode('UTF-8')


def _unpad(s):
    return s[:-ord(s.decode('UTF-8')[-1])]


def _extract_keys(key_str):
    key_bytes = from_base64(key_str)
    return key_bytes[:-HMAC_SIG_SIZE], key_bytes[-HMAC_SIG_SIZE:]
