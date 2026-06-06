import socket
from protocol import send_file

def upload_file(server_ip, port, filepath):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.")
        return

    # Create a TCP/IP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    print(f"Connecting to {server_ip}:{port}...")
    try:
        client_socket.connect((server_ip, port))
        
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

    if (opt == 1):
        print("Write the path to the file you want to upload")
        file_path = input
        upload_file(DEBIAN_IP, file_path)
    elif (opt == 2):
        print("Da-i un mesaj la iuli sa termie codu")
    else:
        print("Real")