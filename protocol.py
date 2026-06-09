import os
import struct
from crypto_lib import encrypt_bytes, decrypt_bytes, get_stream_encryptor, get_stream_decryptor
BUFFER_SIZE = 8192

def recv_all(sock, num_bytes):
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)

def send_encrypted_line(sock, text, key):
    ciphertext = encrypt_bytes(key, text.encode('utf-8'))
    length_prefix = struct.pack('!I', len(ciphertext))
    sock.sendall(length_prefix + ciphertext)


def recv_encrypted_line(sock, key):
    raw_length = recv_all(sock, 4)
    if not raw_length:
        return None
    msg_length = struct.unpack('!I', raw_length)[0]
    ciphertext = recv_all(sock, msg_length)
    if not ciphertext:
        return None
    try:
        plaintext = decrypt_bytes(key, ciphertext)
        return plaintext.decode('utf-8')
    except ValueError:
        print("Decryption failed! Incorrect key or corrupted data.")
        return None

def send_file(sock, filepath, key, filename=None):
    if filename is None:
        filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    metadata = f"{filename}|{filesize}"
    send_encrypted_line(sock, metadata, key)

    nonce, encryptor = get_stream_encryptor(key)
    sock.sendall(nonce)

    print(f"Sending encrypted '{filename}'...")

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break
            encrypted_chunk = encryptor.encrypt(chunk)
            sock.sendall(encrypted_chunk)

    sock.sendall(encryptor.digest())
    print("Transfer complete.")

def receive_file(sock, save_dir, key):
    metadata = recv_encrypted_line(sock, key)
    if not metadata:
        return None
    filename, filesize_str = metadata.split('|')
    filesize = int(filesize_str)
    print(f"Receiving encrypted '{filename}' ({filesize} bytes)...")
    filepath = os.path.join(save_dir, filename)

    nonce = recv_all(sock, 12)
    if not nonce:
        return None
    decryptor = get_stream_decryptor(key, nonce)

    bytes_received = 0
    with open(filepath, 'wb') as f:
        while bytes_received < filesize:
            chunk_size = min(BUFFER_SIZE, filesize - bytes_received)
            encrypted_chunk = recv_all(sock, chunk_size)
            if not encrypted_chunk:
                break
            decrypted_chunk = decryptor.decrypt(encrypted_chunk)
            f.write(decrypted_chunk)
            bytes_received += len(encrypted_chunk)

    if bytes_received == filesize:
        tag = recv_all(sock, 16)
        try:
            decryptor.verify(tag)
            return filepath
        except ValueError:
            print("File was corrupted or tampered with in transit!")
            os.remove(filepath)
            return None