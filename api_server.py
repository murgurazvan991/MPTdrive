import os
import socket
import tempfile
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import the functions from your custom protocol
from protocol import send_file, recv_line, send_line

# --- Configuration ---
# The address of your main TCP server
TCP_SERVER_IP = "127.0.0.1"
TCP_SERVER_PORT = 8080

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

@app.route('/api/files', defaults={'subpath': ''})
@app.route('/api/files/<path:subpath>')
def list_files(subpath):
    """API endpoint to list files in a directory."""
    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    try:
        send_line(sock, 'NAV')
        # Navigate to the correct subdirectory if specified
        if subpath:
            parts = subpath.split('/')
            for part in parts:
                if part == '..':
                    send_line(sock, 'BACK')
                else:
                    send_line(sock, f'ENTER:{part}')
                recv_line(sock) # Consume the listing response for each step

        # Get the final listing
        listing_str = recv_line(sock)
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

    sock = create_tcp_connection()
    if not sock:
        return jsonify({"error": "Could not connect to the storage server"}), 500

    # We must save the file temporarily so we can get its size and path
    # for the send_file protocol function.
    filename = secure_filename(file.filename)
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        file.save(tmp.name)
        try:
            send_line(sock, 'UPLOAD')
            send_file(sock, tmp.name) # Use your protocol to send the file
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
        
        send_line(sock, 'NAV')
        recv_line(sock) # consume initial listing

        for part in path_parts:
            send_line(sock, f'ENTER:{part}')
            recv_line(sock) # consume listing

        # Request the file
        send_line(sock, f'GET:{filename}')

        # Now, we stream the response. First, read the metadata header.
        metadata = recv_line(sock)
        if not metadata or '|' not in metadata:
            return jsonify({"error": "File not found or invalid response from server"}), 404

        _name, filesize_str = metadata.split('|')
        filesize = int(filesize_str)

        # This generator function reads from the socket and yields data to the browser
        def generate():
            bytes_read = 0
            while bytes_read < filesize:
                chunk = sock.recv(4096)
                if not chunk: break
                bytes_read += len(chunk)
                yield chunk
            sock.close()

        # Return a streaming response
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return Response(generate(), mimetype='application/octet-stream', headers=headers)

    except Exception as e:
        sock.close()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Host '0.0.0.0' makes it accessible from any device on your network.
    # The port should be different from your TCP server's port.
    app.run(host='0.0.0.0', port=5000, debug=True)