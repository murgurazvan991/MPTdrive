import os

BUFFER_SIZE = 8192


def send_line(sock, text):
    """Send a UTF-8 encoded line terminated with '\n'."""
    if not text.endswith('\n'):
        text = text + '\n'
    sock.sendall(text.encode('utf-8'))


def recv_line(sock):
    """Receive bytes until '\n' and return the decoded line without the trailing newline.

    Returns `None` if the connection is closed and no bytes were read.
    """
    data = bytearray()
    last = None
    while True:
        b = sock.recv(1)
        last = b
        if not b:
            break
        if b == b'\n':
            break
        data += b
    if not data and not last:
        return None
    return data.decode('utf-8')

def send_file(sock, filepath):
    """Reads a file and sends it over the socket using the custom protocol."""
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # 1. Construct and send metadata
    metadata = f"{filename}|{filesize}\n"
    # sendall() is crucial in Python TCP; it ensures all bytes are sent
    sock.sendall(metadata.encode('utf-8')) 

    cnt = 1
    # 2. Stream the file data in chunks
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break # End of file
            print(f"Sending chunk {cnt} of size {len(chunk)} bytes...")
            sock.sendall(chunk)
            cnt += 1

def receive_file(sock, save_dir):
    """Reads metadata and file bytes from the socket, saving it to disk."""
    # 1. Read metadata byte-by-byte until we hit the newline
    metadata_bytes = bytearray()
    while True:
        byte = sock.recv(1)
        if not byte or byte == b'\n':
            break
        metadata_bytes += byte

    if not metadata_bytes:
        return False

    # Parse the metadata
    metadata = metadata_bytes.decode('utf-8')
    filename, filesize_str = metadata.split('|')
    filesize = int(filesize_str)

    print(f"Receiving '{filename}' ({filesize} bytes)...")

    # 2. Read the file data
    filepath = os.path.join(save_dir, filename)
    bytes_received = 0

    with open(filepath, 'wb') as f:
        while bytes_received < filesize:
            # Only ask for the remaining bytes if we are near the end
            chunk_size = min(BUFFER_SIZE, filesize - bytes_received)
            chunk = sock.recv(chunk_size)
            if not chunk:
                break # Connection dropped prematurely
            
            f.write(chunk)
            bytes_received += len(chunk)

    return True