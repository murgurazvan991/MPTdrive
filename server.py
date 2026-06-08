import socket
import os
from protocol import receive_file, send_file, recv_line, send_line

# Define where files should be saved on the Debian machine
SAVE_DIR = "/home/iulian/Documents"
os.makedirs(SAVE_DIR, exist_ok=True)

def start_server(host='0.0.0.0', port=8080):
    # Create a TCP/IP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Allow the port to be reused immediately after restarting the script
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Storage server listening on port {port}...")

    while True:
        # Wait for a connection
        client_socket, addr = server_socket.accept()
        print(f"\nAccepted connection from {addr}")
        
        try:
            handle_client(client_socket)
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            client_socket.close()

def send_file_tree(path, socket):
    """Send a single-line directory listing for `path` relative to SAVE_DIR.

    Format: entries separated by '::'. Directories have a trailing '/'.
    The line is terminated with a single '\n'.
    """
    if path == "":
        base = SAVE_DIR
    else:
        base = os.path.join(SAVE_DIR, path)

    try:
        entries = os.listdir(base)
    except FileNotFoundError:
        entries = []

    items = []
    # Include parent if not at root
    if os.path.abspath(base) != os.path.abspath(SAVE_DIR):
        items.append('..')

    for e in entries:
        full = os.path.join(base, e)
        if os.path.isdir(full):
            items.append(e + '/')
        else:
            items.append(e)

    line = '::'.join(items)
    send_line(socket, line)


# recv_line moved to protocol.recv_line for reuse


def handle_client(client_socket):
    """Handle a single client connection supporting upload and navigation/download."""
    # Read initial command
    cmd = recv_line(client_socket)
    if cmd is None:
        return

    if cmd == 'UPLOAD':
        # Client will send a file with our existing protocol
        if receive_file(client_socket, SAVE_DIR):
            print("File upload complete!")
        else:
            print("Failed to receive uploaded file.")
        return

    if cmd == 'NAV':
        cur_path = ""
        # Send initial listing
        send_file_tree(cur_path, client_socket)

        while True:
            line = recv_line(client_socket)
            if line is None:
                break
            if line == 'QUIT':
                break
            # ENTER:<name> to descend into a directory
            if line.startswith('ENTER:'):
                name = line.split(':', 1)[1]
                # sanitize: prevent escaping SAVE_DIR
                if name == '..':
                    # go up
                    cur_path = os.path.dirname(cur_path)
                else:
                    # append directory name
                    cur_path = os.path.join(cur_path, name)
                # normalize
                cur_path = os.path.normpath(cur_path)
                if cur_path == '.' or cur_path == '/':
                    cur_path = ""
                send_file_tree(cur_path, client_socket)
                continue

            # BACK command
            if line == 'BACK':
                cur_path = os.path.dirname(cur_path)
                cur_path = os.path.normpath(cur_path)
                if cur_path == '.' or cur_path == '/':
                    cur_path = ""
                send_file_tree(cur_path, client_socket)
                continue

            # GET:<name> to request a file from current directory
            if line.startswith('GET:'):
                name = line.split(':', 1)[1]
                # full path
                if cur_path == "":
                    full = os.path.join(SAVE_DIR, name)
                else:
                    full = os.path.join(SAVE_DIR, cur_path, name)
                full = os.path.normpath(full)
                # ensure file is inside SAVE_DIR
                if not full.startswith(os.path.abspath(SAVE_DIR)):
                    # invalid request
                    client_socket.sendall(b'\n')
                    continue
                if os.path.isfile(full):
                    # Use protocol.send_file to send metadata + bytes
                    send_file(client_socket, full)
                    # After sending the file, resend the current directory listing
                    send_file_tree(cur_path, client_socket)
                else:
                    # send empty line to signal failure
                    client_socket.sendall(b'\n')
                    # resend listing so client can continue
                    send_file_tree(cur_path, client_socket)
                # After sending file, continue; client will handle next listing or quit
                continue

            # Unknown command: ignore or break
            break



if __name__ == "__main__":
    print(os.listdir(SAVE_DIR))
    start_server()