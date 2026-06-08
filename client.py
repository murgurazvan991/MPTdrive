import socket
import os
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
        print(f"Uploading '{filepath}'...")
        send_file(client_socket, filepath)
        
        print("Upload complete!")
    except ConnectionRefusedError:
        print("Error: Could not connect to the server. Is it running?")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()

if __name__ == "__main__":
    import os # Needed for the file check in this script
    
    # Replace this with the local IP of your Debian server
    DEBIAN_IP = "127.0.0.1" 
    PORT = 8080
    FILE_TO_UPLOAD = "/home/razvan/Documents/test.cpp" # Replace with a real file on your system

    print("Press:")
    print("1) To upload a file")
    print("2) To download a file")
    opt = input()

    if (opt == "1"):
        print("Write the path to the file you want to upload")
        file_path = input()
        upload_file(DEBIAN_IP, PORT, file_path)
    elif (opt == "2"):
        # Launch interactive navigation + download session
        # use recv_line from protocol
        def navigate_and_download(server_ip, port, save_dir):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((server_ip, port))
                # start navigation session
                send_line(sock, 'NAV')

                while True:
                    listing = recv_line(sock)
                    if listing is None:
                        print('Connection closed by server')
                        break

                    # If the server sends file metadata (contains '|'), delegate to receive_file
                    if '|' in listing:
                        # turn the previously-read line back into a stream for receive_file is complex;
                        # our server sends metadata only when client asked for GET, so we shouldn't reach here.
                        pass

                    items = [] if listing.strip() == '' else listing.strip().split('::')
                    print('\nRemote directory:')
                    for i, it in enumerate(items, start=1):
                        print(f"{i}) {it}")
                    print('\nOptions:')
                    print("Enter number to navigate into a directory or download a file")
                    print("Prefix with 'd' to download by number (e.g. d3), 'b' to go back, 'q' to quit")

                    choice = input('> ').strip()
                    if choice == 'q':
                        send_line(sock, 'QUIT')
                        break
                    if choice == 'b':
                        send_line(sock, 'BACK')
                        continue
                    if choice.startswith('d'):
                        # download
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
                        # request file
                        send_line(sock, f'GET:{name}')
                        # use protocol.receive_file to accept the incoming file and save into save_dir
                        if receive_file(sock, save_dir):
                            print('Download complete')
                        else:
                            print('Download failed')
                        # after download continue navigation
                        continue

                    # plain number: navigate into directory or download if it's a file
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
                        # enter directory (strip trailing slash)
                        name = sel[:-1]
                        send_line(sock, f'ENTER:{name}')
                        continue
                    else:
                        # file selected — ask whether to download
                        yn = input(f"Download '{sel}'? [y/N] ").strip().lower()
                        if yn == 'y':
                            send_line(sock, f'GET:{sel}')
                            if receive_file(sock, save_dir):
                                print('Download complete')
                            else:
                                print('Download failed')
                        else:
                            print('Skipped')

            except ConnectionRefusedError:
                print('Could not connect to server')
            finally:
                sock.close()

        # Ask where to save
        save_dir = os.getcwd()
        print(f"Files will be saved to: {save_dir}")
        navigate_and_download(DEBIAN_IP, PORT, save_dir)
    else:
        print("Real")