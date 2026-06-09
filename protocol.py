import os
import struct
from crypto_lib import encrypt_bytes, decrypt_bytes, get_stream_encryptor, get_stream_decryptor
BUFFER_SIZE = 8192

def recv_all(sock, num_bytes):
    """Helper to cleanly read an exact number of bytes from the socket."""
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)

def send_encrypted_line(sock, text, key):
    """Encrypts text and sends it with a 4-byte length prefix."""
    # 1. Encrypt the string
    ciphertext = encrypt_bytes(key, text.encode('utf-8'))
    # 2. Get the length of the ciphertext and pack it into 4 bytes (!I = Network Byte Order, Unsigned Int)
    length_prefix = struct.pack('!I', len(ciphertext))
    # 3. Send length + ciphertext
    sock.sendall(length_prefix + ciphertext)


def recv_encrypted_line(sock, key):
    """Reads the length prefix, reads the exact ciphertext, and decrypts it."""
    # 1. Read the 4-byte length
    raw_length = recv_all(sock, 4)
    if not raw_length:
        return None
    msg_length = struct.unpack('!I', raw_length)[0]
    
    # 2. Read exactly 'msg_length' bytes of ciphertext
    ciphertext = recv_all(sock, msg_length)
    if not ciphertext:
        return None
        
    # 3. Decrypt and return as string
    try:
        plaintext = decrypt_bytes(key, ciphertext)
        return plaintext.decode('utf-8')
    except ValueError:
        print("Decryption failed! Incorrect key or corrupted data.")
        return None

def send_file(sock, filepath, key, filename=None):
    """Encrypts and streams a file over the socket on the fly."""
    if filename is None:
        filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # 1. Send encrypted metadata (hides the filename and size from network snoopers!)
    metadata = f"{filename}|{filesize}"
    send_encrypted_line(sock, metadata, key)

    # 2. Set up the AES-GCM cipher
    nonce, encryptor = get_stream_encryptor(key)
    
    # Send the nonce first so the receiver can set up their lock
    sock.sendall(nonce)

    print(f"Sending encrypted '{filename}'...")

    # 3. Stream and encrypt the file chunks
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break 
            # Use the encryptor object
            encrypted_chunk = encryptor.encrypt(chunk)
            sock.sendall(encrypted_chunk)

    # 4. Send the 16-byte authentication tag at the very end
    sock.sendall(encryptor.digest())
    print("Transfer complete.")

def receive_file(sock, save_dir, key):
    """Reads, decrypts, and verifies a file streamed over the socket."""
    # 1. Read the encrypted metadata
    metadata = recv_encrypted_line(sock, key)
    if not metadata:
        return None
        
    filename, filesize_str = metadata.split('|')
    filesize = int(filesize_str)
    
    print(f"Receiving encrypted '{filename}' ({filesize} bytes)...")
    filepath = os.path.join(save_dir, filename)

    # 2. Read the nonce and set up the AES-GCM decryption cipher
    nonce = recv_all(sock, 12)
    if not nonce:
        return None
        
    decryptor = get_stream_decryptor(key, nonce)

    # 3. Stream, decrypt, and save the chunks
    bytes_received = 0
    with open(filepath, 'wb') as f:
        while bytes_received < filesize:
            chunk_size = min(BUFFER_SIZE, filesize - bytes_received)
            encrypted_chunk = recv_all(sock, chunk_size)
            if not encrypted_chunk:
                break 
            
            # Use the decryptor object
            decrypted_chunk = decryptor.decrypt(encrypted_chunk)
            f.write(decrypted_chunk)
            bytes_received += len(encrypted_chunk)

    # 4. Verify the file's integrity using the tag
    if bytes_received == filesize:
        tag = recv_all(sock, 16)
        try:
            decryptor.verify(tag)
            return filepath
        except ValueError:
            print("File was corrupted or tampered with in transit!")
            os.remove(filepath)
            return None