import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

# AES-GCM parameters
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 64 * 1024


def _validate_key(key: bytes):
    """Ensures the key is the correct type and length for AES."""
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("key must be bytes")
    if len(key) not in (16, 24, 32):
        raise ValueError("Key length must be 16, 24, or 32 bytes")


def encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    """Return payload = nonce || ciphertext || tag"""
    _validate_key(key)
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext must be bytes")

    nonce = get_random_bytes(NONCE_SIZE)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct = cipher.encrypt(plaintext)
    tag = cipher.digest()
    return nonce + ct + tag


def decrypt_bytes(key: bytes, payload: bytes) -> bytes:
    """Parse payload = nonce || ciphertext || tag and return plaintext."""
    _validate_key(key)
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    if len(payload) < NONCE_SIZE + TAG_SIZE:
        raise ValueError("payload too short")

    nonce = payload[:NONCE_SIZE]
    tag = payload[-TAG_SIZE:]
    ct = payload[NONCE_SIZE:-TAG_SIZE]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ct, tag)


def encrypt_file(input_path: str, output_path: str, key: bytes) -> None:
    """Stream-encrypt a file using AES-GCM.

    Format written: nonce (12 bytes) || ciphertext (streamed) || tag (16 bytes)
    """
    _validate_key(key)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(input_path)

    nonce = get_random_bytes(NONCE_SIZE)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

    with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            fout.write(cipher.encrypt(chunk))
        fout.write(cipher.digest())


def decrypt_file(input_path: str, output_path: str, key: bytes) -> None:
    """Decrypt a file written by `encrypt_file`.

    This reads the nonce, then the ciphertext+tag (the function reads the rest
    of the file into memory to separate tag).
    """
    _validate_key(key)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(input_path)

    with open(input_path, 'rb') as fin:
        nonce = fin.read(NONCE_SIZE)
        rest = fin.read()

    if len(nonce) != NONCE_SIZE or len(rest) < TAG_SIZE:
        raise ValueError("input file is corrupted or too short")

    tag = rest[-TAG_SIZE:]
    ct = rest[:-TAG_SIZE]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ct, tag)

    with open(output_path, 'wb') as fout:
        fout.write(plaintext)

def get_stream_encryptor(key: bytes):
    """Sets up an on-the-fly encryption stream.
    Returns a tuple: (nonce_to_send, encryptor_object)
    """
    _validate_key(key)
    nonce = get_random_bytes(NONCE_SIZE)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return nonce, cipher

def get_stream_decryptor(key: bytes, nonce: bytes):
    """Sets up an on-the-fly decryption stream.
    Returns: decryptor_object
    """
    _validate_key(key)
    if len(nonce) != NONCE_SIZE:
        raise ValueError("Invalid nonce length")
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher