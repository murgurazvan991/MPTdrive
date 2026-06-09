import argparse
import socket
import os
from archive_utils import create_tar, safe_extract_tar, is_archive_name
from protocol import send_file, receive_file, recv_line, send_line

def upload_file(server_ip, port, filepath):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        return

    # Create a TCP/IP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    print(f"Connecting to {server_ip}:{port}...")
    try:
        client_socket.connect((server_ip, port))
        # tell server we want to upload
        send_line(client_socket, 'UPLOAD')

        # If the path is a directory, create a tar.gz and send that
        if os.path.isdir(filepath):
            tmp_name = create_tar(filepath)
            print(f"Uploading directory '{filepath}' as archive {tmp_name}...")
            try:
                send_file(client_socket, tmp_name)
            finally:
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
        else:
            print(f"Uploading '{filepath}'...")
            send_file(client_socket, filepath)

        print("Upload complete!")
    except ConnectionRefusedError:
        print("Error: Could not connect to the server. Is it running?")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()
def navigate_and_download(server_ip, port, save_dir):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((server_ip, port))
        send_line(sock, 'NAV')

        while True:
            # OUTER LOOP: Only for fetching listings from the server
            listing = recv_line(sock)
            if listing is None:
                print('Connection closed by server')
                break

            items = [] if listing.strip() == '' else listing.strip().split('::')
            print('\nRemote directory:')
            for i, it in enumerate(items, start=1):
                print(f"{i}) {it}")
            print('\nOptions:')
            print("Enter number to navigate into a directory or download a file")
            print("Prefix with 'd' to download by number (e.g. d3), 't' to download a directory as tar (e.g. t2), 'u /local/path' to upload a local file/dir into current remote directory, 'save /path' to change local download directory, 'b' to go back, 'q' to quit")

            # INNER LOOP: For handling user input and local commands
            while True:
                choice = input('> ').strip()

                # 1. LOCAL COMMAND: Change save directory
                if choice.startswith('save ') or choice.startswith('sd '):
                    parts = choice.split(None, 1)
                    if len(parts) < 2:
                        print('Usage: save /path/to/save')
                        continue
                    new_dir = parts[1]
                    try:
                        os.makedirs(new_dir, exist_ok=True)
                        save_dir = new_dir
                        print(f'Download directory set to: {save_dir}')
                    except Exception as e:
                        print('Could not set save directory:', e)
                    continue # Loops back to input without waiting for server!

                # 2. SERVER COMMAND: Upload
                if choice.startswith('u ') or choice.startswith('upload '):
                    parts = choice.split(None, 1)
                    if len(parts) < 2:
                        print('Usage: u /path/to/local/file_or_dir')
                        continue
                    local_path = parts[1]
                    if not os.path.exists(local_path):
                        print('Local path does not exist')
                        continue
                    
                    if os.path.isdir(local_path):
                        send_path = create_tar(local_path)
                        remove_after = True
                    else:
                        send_path = local_path
                        remove_after = False

                    try:
                        send_line(sock, 'UPLOAD_HERE')
                        send_file(sock, send_path)
                        print('Upload sent')
                    except Exception as e:
                        print('Upload failed:', e)
                    finally:
                        if remove_after:
                            try:
                                os.remove(send_path)
                            except Exception:
                                pass
                    break # Breaks inner loop to fetch new listing from server

                # 3. SERVER COMMAND: Quit
                if choice == 'q':
                    send_line(sock, 'QUIT')
                    return # Exits the function entirely

                # 4. SERVER COMMAND: Back
                if choice == 'b':
                    send_line(sock, 'BACK')
                    break # Breaks inner loop

                # 5. SERVER COMMAND: Download by prefix
                if choice.startswith('d'):
                    try:
                        idx = int(choice[1:]) - 1
                    except Exception:
                        print('Invalid selection')
                        continue
                    if idx < 0 or idx >= len(items):
                        print('Index out of range')
                        continue
                    name = items[idx]
                    if name.endswith('/'):
                        print('Selected item is a directory; cannot download. Enter it instead.')
                        continue
                    send_line(sock, f'GET:{name}')
                    saved = receive_file(sock, save_dir)
                    if saved:
                        if saved.endswith(('.tar.gz', '.tgz', '.tar')):
                            try:
                                safe_extract_tar(saved, save_dir)
                                os.remove(saved)
                                print('Archive downloaded and extracted')
                            except Exception as e:
                                print('Extraction failed:', e)
                        else:
                            print(f'Download complete: {saved}')
                    else:
                        print('Download failed')
                    break # Breaks inner loop

                # 6. SERVER COMMAND: Tar download
                if choice.startswith('t'):
                    try:
                        idx = int(choice[1:]) - 1
                    except Exception:
                        print('Invalid selection')
                        continue
                    if idx < 0 or idx >= len(items):
                        print('Index out of range')
                        continue
                    name = items[idx]
                    if not name.endswith('/'):
                        print('Selected item is not a directory')
                        continue
                    name = name[:-1]
                    send_line(sock, f'TAR:{name}')
                    saved = receive_file(sock, save_dir)
                    if saved:
                        try:
                            safe_extract_tar(saved, save_dir)
                            os.remove(saved)
                            print('Directory downloaded and extracted')
                        except Exception as e:
                            print('Extraction failed:', e)
                    else:
                        print('Tar download failed')
                    break # Breaks inner loop

                # 7. SERVER COMMAND: Numeric selection (Enter or Download)
                try:
                    idx = int(choice) - 1
                except Exception:
                    print('Invalid input')
                    continue
                if idx < 0 or idx >= len(items):
                    print('Index out of range')
                    continue
                sel = items[idx]
                
                if sel.endswith('/'):
                    name = sel[:-1]
                    send_line(sock, f'ENTER:{name}')
                    break # Breaks inner loop
                else:
                    yn = input(f"Download '{sel}'? [y/N] ").strip().lower()
                    if yn == 'y':
                        send_line(sock, f'GET:{sel}')
                        saved = receive_file(sock, save_dir)
                        if saved:
                            if saved.endswith(('.tar.gz', '.tgz', '.tar')):
                                try:
                                    safe_extract_tar(saved, save_dir)
                                    os.remove(saved)
                                    print('Archive downloaded and extracted')
                                except Exception as e:
                                    print('Extraction failed:', e)
                            else:
                                print(f'Download complete: {saved}')
                        else:
                            print('Download failed')
                        break # Breaks inner loop
                    else:
                        print('Skipped')
                        continue # Loops back to input since we skipped!

    except ConnectionRefusedError:
        print('Could not connect to server')
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='client.py', description='MPTdrive client — NAV UI')
    parser.add_argument('--server', '-S', default='127.0.0.1', help='Server IP (default: 127.0.0.1)')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Server port (default: 8080)')
    parser.add_argument('--save-dir', '-s', default=os.getcwd(), help='Local directory to save downloads (default: current working directory)')
    args = parser.parse_args()

    DEBIAN_IP = args.server
    PORT = args.port
    save_dir = args.save_dir
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception as e:
        print('Could not create save directory, using cwd instead:', e)
        save_dir = os.getcwd()

    print(f"Files will be saved to: {save_dir}")
    navigate_and_download(DEBIAN_IP, PORT, save_dir)