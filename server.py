import socket
import os
from protocol import receive_file

# Define where files should be saved on the Debian machine
SAVE_DIR = "/home/razvan/facultate/retele/server_files"
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
            if receive_file(client_socket, SAVE_DIR):
                print("File transfer complete!")
            else:
                print("Failed to receive file.")
        except Exception as e:
            print(f"Transfer error: {e}")
        finally:
            client_socket.close()

def send_file_tree(path, socket):
    msg = ""
    if (path == ""):
        msg = (os.listdir(SAVE_DIR))
    else:
        msg = (os.listdir(SAVE_DIR + "/" + path))
    #trimite mesaju


if __name__ == "__main__":
    print(os.listdir(SAVE_DIR))
    start_server()