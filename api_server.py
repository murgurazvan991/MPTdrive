import os
import socket
import tempfile
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import the functions from your custom protocol
from config import KEY
from crypto_lib import get_stream_decryptor
from protocol import send_file, recv_all, recv_encrypted_line, send_encrypted_line

# --- Configuration ---
# The Docker service name for the storage server is provided through environment.
TCP_SERVER_IP = os.environ.get("TCP_SERVER_HOST", "127.0.0.1")
TCP_SERVER_PORT = int(os.environ.get("TCP_SERVER_PORT", "8080"))

app = Flask(__name__)
# This is crucial for allowing your React app (e.g., from localhost:3000)
# to make requests to this API server (e.g., on localhost:5000)
CORS(app)

def create_tcp_connection():
    """A helper function to connect to your main TCP server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((TCP_SERVER_IP, TCP_SERVER_PORT))
        return sock
    except ConnectionRefusedError:
        return None

@app.route('/api/files', defaults={'subpath': ''}, strict_slashes=False)
@app.route('/api/files/<path:subpath>')
def list_files(subpath):
    """API endpoint to list files in a directory."""
    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    try:
        send_encrypted_line(sock, 'NAV', KEY)
        # Navigate to the correct subdirectory if specified
        if subpath:
            parts = subpath.split('/')
            for part in parts:
                if part == '..':
                    send_encrypted_line(sock, 'BACK', KEY)
                else:
                    send_encrypted_line(sock, f'ENTER:{part}', KEY)
                recv_encrypted_line(sock, KEY) # Consume the listing response for each step

        # Get the final listing
        listing_str = recv_encrypted_line(sock, KEY)
        items = [] if not listing_str or listing_str.strip() == '' else listing_str.strip().split('::')
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        sock.close()

@app.route('/api/upload', methods=['POST'])
def upload_file_endpoint():
    """API endpoint to handle file uploads."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    target_path = request.args.get('path', '')

    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    # We must save the file temporarily so we can get its size and path
    # for the send_file protocol function.
    filename = secure_filename(file.filename)
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        file.save(tmp.name)
        try:
            if target_path:
                send_encrypted_line(sock, 'NAV', KEY)
                parts = target_path.split('/')
                for part in parts:
                    if part == '..':
                        send_encrypted_line(sock, 'BACK', KEY)
                    else:
                        send_encrypted_line(sock, f'ENTER:{part}', KEY)
                    recv_encrypted_line(sock, KEY)
                send_encrypted_line(sock, 'UPLOAD_HERE', KEY)
            else:
                send_encrypted_line(sock, 'UPLOAD', KEY)

            send_file(sock, tmp.name, KEY, filename=filename) # Preserve original filename
        except Exception as e:
            return jsonify({"error": f"TCP communication failed: {e}"}), 500
        finally:
            sock.close()

    return jsonify({"message": f"File '{filename}' uploaded successfully."})

@app.route('/api/download/<path:filepath>')
def download_file(filepath):
    """API endpoint to stream a file download."""
    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    try:
        # Navigate to the file's location
        path_parts = filepath.split('/')
        filename = path_parts.pop()
        
        send_encrypted_line(sock, 'NAV', KEY)
        recv_encrypted_line(sock, KEY) # consume initial listing

        for part in path_parts:
            send_encrypted_line(sock, f'ENTER:{part}', KEY)
            recv_encrypted_line(sock, KEY) # consume listing

        # Request the file
        send_encrypted_line(sock, f'GET:{filename}', KEY)

        # Now, we stream the response. First, read the metadata header.
        metadata = recv_encrypted_line(sock, KEY)
        if not metadata or '|' not in metadata:
            return jsonify({"error": "File not found or invalid response from server"}), 404

        _name, filesize_str = metadata.split('|')
        filesize = int(filesize_str)

        # Read the AES-GCM nonce from the stream
        nonce = recv_all(sock, 12)
        if not nonce or len(nonce) != 12:
            return jsonify({"error": "Invalid file stream from storage server"}), 500

        decryptor = get_stream_decryptor(KEY, nonce)

        # This generator function reads from the socket, decrypts it, and yields plaintext.
        def generate():
            bytes_read = 0
            while bytes_read < filesize:
                to_read = min(4096, filesize - bytes_read)
                encrypted_chunk = recv_all(sock, to_read)
                if not encrypted_chunk:
                    break
                bytes_read += len(encrypted_chunk)
                yield decryptor.decrypt(encrypted_chunk)

            tag = recv_all(sock, 16)
            decryptor.verify(tag)
            # Read and discard the follow-up listing from the storage server
            try:
                recv_encrypted_line(sock, KEY)
            except Exception:
                pass
            finally:
                sock.close()

        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return Response(generate(), mimetype='application/octet-stream', headers=headers)

    except Exception as e:
        sock.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-directory/<path:dirpath>')
def download_directory(dirpath):
    """API endpoint to stream a directory as a tar.gz archive."""
    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    try:
        path_parts = dirpath.split('/')
        dirname = path_parts.pop()

        send_encrypted_line(sock, 'NAV', KEY)
        recv_encrypted_line(sock, KEY)

        for part in path_parts:
            send_encrypted_line(sock, f'ENTER:{part}', KEY)
            recv_encrypted_line(sock, KEY)

        send_encrypted_line(sock, f'TAR:{dirname}', KEY)

        metadata = recv_encrypted_line(sock, KEY)
        if not metadata or '|' not in metadata:
            return jsonify({"error": "Directory not found or invalid response from server"}), 404

        _name, filesize_str = metadata.split('|')
        filesize = int(filesize_str)

        nonce = recv_all(sock, 12)
        if not nonce or len(nonce) != 12:
            return jsonify({"error": "Invalid file stream from storage server"}), 500

        decryptor = get_stream_decryptor(KEY, nonce)

        def generate():
            bytes_read = 0
            while bytes_read < filesize:
                to_read = min(4096, filesize - bytes_read)
                encrypted_chunk = recv_all(sock, to_read)
                if not encrypted_chunk:
                    break
                bytes_read += len(encrypted_chunk)
                yield decryptor.decrypt(encrypted_chunk)

            tag = recv_all(sock, 16)
            decryptor.verify(tag)
            try:
                recv_encrypted_line(sock, KEY)
            except Exception:
                pass
            finally:
                sock.close()

        headers = {"Content-Disposition": f"attachment; filename={dirname}.tar.gz"}
        return Response(generate(), mimetype='application/gzip', headers=headers)

    except Exception as e:
        sock.close()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Host '0.0.0.0' makes it accessible from any device on your network.
    # The port should be different from your TCP server's port.
    app.run(host='0.0.0.0', port=5000, debug=True)