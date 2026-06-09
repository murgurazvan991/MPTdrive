import React, { useState, useEffect } from 'react';
import './App.css'; // We'll add some basic styles

// --- Configuration ---
// Use a relative API path so Vite can proxy requests to the Flask backend.
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

function App() {
  const [files, setFiles] = useState([]);
  const [currentPath, setCurrentPath] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [directoryFiles, setDirectoryFiles] = useState([]);

  // Function to fetch the list of files from the backend
  const fetchFiles = (path) => {
    setStatusMessage('Loading...');
    const pathSegment = path ? `/${path}` : '';
    fetch(`${API_BASE}/files${pathSegment}`)
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        setFiles(data);
        setCurrentPath(path);
        setStatusMessage('');
      })
      .catch(error => {
        console.error('Error fetching files:', error);
        setStatusMessage(`Error: Could not fetch files. Is the API server running?`);
      });
  };

  // This effect runs once when the component first loads
  useEffect(() => {
    fetchFiles(''); // Fetch the root directory initially
  }, []);

  // Handler for when a user clicks on a file or directory
  const handleItemClick = (item) => {
    if (item.endsWith('/')) { // It's a directory
      const dirName = item.slice(0, -1);
      const newPath = currentPath ? `${currentPath}/${dirName}` : dirName;
      fetchFiles(newPath);
    } else if (item === '..') { // Go back
      const pathParts = currentPath.split('/');
      pathParts.pop();
      const newPath = pathParts.join('/');
      fetchFiles(newPath);
    } else {
      // It's a file, so we construct the download URL
      const downloadPath = currentPath ? `${currentPath}/${item}` : item;
      window.location.href = `${API_BASE}/download/${downloadPath}`;
    }
  };

  const downloadDirectory = (item) => {
    const dirName = item.slice(0, -1);
    const downloadPath = currentPath ? `${currentPath}/${dirName}` : dirName;
    window.location.href = `${API_BASE}/download-directory/${downloadPath}`;
  };

  // Handler for the file input change
  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
  };

  const handleDirChange = (event) => {
    const files = Array.from(event.target.files);
    setDirectoryFiles(files);
    setStatusMessage(`${files.length} files selected for directory upload.`);
  };

  const pad = (value, length) => {
    const s = typeof value === 'string' ? value : String(value);
    return s.padStart(length, '0');
  };

  const buildTarHeader = (name, size) => {
    const encoder = new TextEncoder();
    const buf = new Uint8Array(512);

    const writeString = (str, offset, length) => {
      const encoded = encoder.encode(str);
      buf.set(encoded.slice(0, length), offset);
    };

    let nameField = name;
    let prefixField = '';
    if (nameField.length > 100) {
      const idx = nameField.slice(0, 100).lastIndexOf('/');
      if (idx === -1 || nameField.length - idx - 1 > 100) {
        throw new Error('Directory path too long for tar header');
      }
      prefixField = nameField.slice(0, idx);
      nameField = nameField.slice(idx + 1);
    }

    writeString(nameField, 0, 100);
    writeString(`${pad(0, 7)}\0`, 100, 8); // mode
    writeString(`${pad(0, 7)}\0`, 108, 8); // uid
    writeString(`${pad(0, 7)}\0`, 116, 8); // gid
    writeString(`${pad(size.toString(8), 11)}\0`, 124, 12);
    writeString(`${pad(Math.floor(Date.now() / 1000).toString(8), 11)}\0`, 136, 12);
    writeString('        ', 148, 8); // checksum placeholder
    writeString('0', 156, 1);
    writeString('ustar\0', 257, 6);
    writeString('00', 263, 2);
    writeString('root', 265, 32);
    writeString('root', 297, 32);
    writeString(prefixField, 345, 155);

    let sum = 0;
    for (let i = 0; i < 512; i += 1) {
      sum += buf[i];
    }
    const checksum = `${pad(sum.toString(8), 6)}\0 `;
    writeString(checksum, 148, 8);
    return buf;
  };

  const createTarBlob = async (files) => {
    const parts = [];
    let sizeSum = 0;

    for (const file of files) {
      const filePath = file.webkitRelativePath || file.name;
      const header = buildTarHeader(filePath, file.size);
      parts.push(header);
      parts.push(await file.arrayBuffer());
      const remainder = file.size % 512;
      if (remainder !== 0) {
        parts.push(new Uint8Array(512 - remainder));
      }
      sizeSum += file.size;
    }

    parts.push(new Uint8Array(512));
    parts.push(new Uint8Array(512));
    return new Blob(parts, { type: 'application/x-tar' });
  };

  const handleUpload = (event) => {
    event.preventDefault(); // Prevent the form from reloading the page
    if (!selectedFile) {
      setStatusMessage('Please select a file to upload.');
      return;
    }

    setStatusMessage('Uploading...');
    const formData = new FormData();
    formData.append('file', selectedFile);
    const targetQuery = currentPath ? `?path=${encodeURIComponent(currentPath)}` : '';

    fetch(`${API_BASE}/upload${targetQuery}`, {
      method: 'POST',
      body: formData,
    })
    .then(response => response.json())
    .then(data => {
      setStatusMessage(data.message || 'Upload complete!');
      setSelectedFile(null); // Reset the file input
      document.getElementById('file-input').value = ''; // Clear the file input visually
      fetchFiles(currentPath); // Refresh the file list
    })
    .catch(error => {
      console.error('Error uploading file:', error);
      setStatusMessage('Error during upload.');
    });
  };

  const handleDirectoryUpload = async (event) => {
    event.preventDefault();
    if (!directoryFiles.length) {
      setStatusMessage('Please select a directory to upload.');
      return;
    }

    setStatusMessage('Packaging directory...');
    let tarBlob;
    try {
      tarBlob = await createTarBlob(directoryFiles);
    } catch (error) {
      console.error('Failed to create tar:', error);
      setStatusMessage('Failed to package the directory.');
      return;
    }

    setStatusMessage('Uploading directory...');
    const formData = new FormData();
    formData.append('file', tarBlob, 'upload-directory.tar');
    const targetQuery = currentPath ? `?path=${encodeURIComponent(currentPath)}` : '';

    fetch(`${API_BASE}/upload${targetQuery}`, {
      method: 'POST',
      body: formData,
    })
    .then(response => response.json())
    .then(data => {
      setStatusMessage(data.message || 'Directory upload complete!');
      setDirectoryFiles([]);
      document.getElementById('dir-input').value = '';
      fetchFiles(currentPath);
    })
    .catch(error => {
      console.error('Error uploading directory:', error);
      setStatusMessage('Error during directory upload.');
    });
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>MPT Drive</h1>
        <p>Current Directory: <code>/{currentPath}</code></p>
      </header>
      <main>
        <div className="file-browser">
          <h2>Files</h2>
          {statusMessage && <p className="status">{statusMessage}</p>}
          <ul>
            {files.map((item, index) => (
              <li key={index}>
                <span onClick={() => handleItemClick(item)} style={{ cursor: 'pointer' }}>
                  {item.endsWith('/') ? '📁' : '📄'} {item}
                </span>
                {item.endsWith('/') && (
                  <button
                    type="button"
                    className="download-dir-button"
                    onClick={() => downloadDirectory(item)}
                  >
                    Download folder
                  </button>
                )}
              </li>
            ))}
            {files.length === 0 && !statusMessage && <li>Directory is empty.</li>}
          </ul>
        </div>
        <div className="upload-section">
          <h2>Upload File</h2>
          <form onSubmit={handleUpload}>
            <input id="file-input" type="file" onChange={handleFileChange} />
            <button type="submit">Upload</button>
          </form>
        </div>
        <div className="upload-section">
          <h2>Upload Directory</h2>
          <form onSubmit={handleDirectoryUpload}>
            <input id="dir-input" type="file" webkitdirectory="true" directory="" multiple onChange={handleDirChange} />
            <button type="submit">Upload Directory</button>
          </form>
        </div>
      </main>
    </div>
  );
}

export default App;
