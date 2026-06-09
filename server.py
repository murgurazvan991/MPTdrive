import socket
import os
from archive_utils import create_tar, safe_extract_tar, is_archive_name
from config import KEY
from protocol import send_file, receive_file, send_encrypted_line, recv_encrypted_line
from var.SAVE_DIR import SAVE_DIR

os.makedirs(SAVE_DIR, exist_ok=True)

def start_server(host='0.0.0.0', port=8080):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Storage server listening on port {port}...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"\nAccepted connection from {addr}")
        try:
            handle_client(client_socket)
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            print(f"Closing connection from {addr}")
            client_socket.close()

def send_file_tree(path, socket):
    if path == "":
        base = SAVE_DIR
    else:
        base = os.path.join(SAVE_DIR, path)

    try:
        entries = os.listdir(base)
    except FileNotFoundError:
        entries = []

    items = []
    if os.path.abspath(base) != os.path.abspath(SAVE_DIR):
        items.append('..')

    for e in entries:
        full = os.path.join(base, e)
        if os.path.isdir(full):
            items.append(e + '/')
        else:
            items.append(e)

    line = '::'.join(items)
    send_encrypted_line(socket, line, KEY)


def handle_client(client_socket):
    cmd = recv_encrypted_line(client_socket, KEY)
    if cmd is None:
        return

    if cmd == 'UPLOAD':
        saved = receive_file(client_socket, SAVE_DIR, KEY)
        if saved:
            print(f"Received uploaded file: {saved}")
            if saved.endswith(('.tar.gz', '.tgz', '.tar')):
                try:
                    safe_extract_tar(saved, SAVE_DIR)
                    os.remove(saved)
                    print("Archive extracted and removed.")
                except Exception as e:
                    print(f"Extraction error: {e}")
        else:
            print("Failed to receive uploaded file.")
        return

    if cmd == 'NAV':
        cur_path = ""
        send_file_tree(cur_path, client_socket)

        while True:
            line = recv_encrypted_line(client_socket, KEY)
            if line is None:
                break
            if line == 'QUIT':
                break
            if line.startswith('ENTER:'):
                name = line.split(':', 1)[1]
                if name == '..':
                    cur_path = os.path.dirname(cur_path)
                else:
                    cur_path = os.path.join(cur_path, name)
                cur_path = os.path.normpath(cur_path)
                if cur_path == '.' or cur_path == '/':
                    cur_path = ""
                send_file_tree(cur_path, client_socket)
                continue

            if line == 'BACK':
                cur_path = os.path.dirname(cur_path)
                cur_path = os.path.normpath(cur_path)
                if cur_path == '.' or cur_path == '/':
                    cur_path = ""
                send_file_tree(cur_path, client_socket)
                continue

            if line.startswith('GET:'):
                name = line.split(':', 1)[1]
                if cur_path == "":
                    full = os.path.join(SAVE_DIR, name)
                else:
                    full = os.path.join(SAVE_DIR, cur_path, name)
                full = os.path.normpath(full)
                if not full.startswith(os.path.abspath(SAVE_DIR)):
                    client_socket.sendall(b'\n')
                    continue
                if os.path.isfile(full):
                    send_file(client_socket, full, KEY)
                    send_file_tree(cur_path, client_socket)
                else:
                    client_socket.sendall(b'\n')
                    send_file_tree(cur_path, client_socket)
                continue

            if line.startswith('TAR:'):
                name = line.split(':', 1)[1]
                if name == '' or name == '.':
                    target = os.path.join(SAVE_DIR, cur_path) if cur_path else SAVE_DIR
                else:
                    if cur_path == '':
                        target = os.path.join(SAVE_DIR, name)
                    else:
                        target = os.path.join(SAVE_DIR, cur_path, name)
                target = os.path.normpath(target)
                if not target.startswith(os.path.abspath(SAVE_DIR)) or not os.path.isdir(target):
                    send_encrypted_line(client_socket, '', KEY)
                    send_file_tree(cur_path, client_socket)
                    continue

                try:
                    tmp_name = create_tar(target)
                    send_file(client_socket, tmp_name, KEY)
                except Exception as e:
                    print(f"Error creating/sending tar: {e}")
                    send_encrypted_line(client_socket, '', KEY)
                finally:
                    try:
                        if 'tmp_name' in locals():
                            os.remove(tmp_name)
                    except Exception:
                        pass
                send_file_tree(cur_path, client_socket)
                continue

            if line.startswith('UPLOAD_HERE'):
                if cur_path == "":
                    target_dir = SAVE_DIR
                else:
                    target_dir = os.path.join(SAVE_DIR, cur_path)
                target_dir = os.path.normpath(target_dir)
                if not target_dir.startswith(os.path.abspath(SAVE_DIR)):
                    send_encrypted_line(client_socket, '', KEY)
                    send_file_tree(cur_path, client_socket)
                    continue

                os.makedirs(target_dir, exist_ok=True)
                saved = receive_file(client_socket, target_dir, KEY)
                if saved:
                    print(f"Received upload into {target_dir}: {saved}")
                    if is_archive_name(saved):
                        try:
                            safe_extract_tar(saved, target_dir)
                            os.remove(saved)
                            print("Archive extracted and removed.")
                        except Exception as e:
                            print(f"Extraction error: {e}")
                else:
                    print("Failed to receive uploaded file in NAV session.")
                send_file_tree(cur_path, client_socket)
                continue

            break



if __name__ == "__main__":
    print(os.listdir(SAVE_DIR))
    start_server()