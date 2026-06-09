import React, { useState, useEffect } from 'react';
import './App.css'; // We'll add some basic styles

// --- Configuration ---
// This should be the IP address of your Debian server where the api_server.py is running.
// If you are running everything on the same machine for development, 'localhost' is fine.
const API_HOST = 'http://localhost:5000';

function App() {
  const [files, setFiles] = useState([]);
  const [currentPath, setCurrentPath] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  // Function to fetch the list of files from the backend
  const fetchFiles = (path) => {
    setStatusMessage('Loading...');
    fetch(`${API_HOST}/api/files/${path}`)
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
      window.location.href = `${API_HOST}/api/download/${downloadPath}`;
    }
  };

  // Handler for the file input change
  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
  };

  // Handler for the upload form submission
  const handleUpload = (event) => {
    event.preventDefault(); // Prevent the form from reloading the page
    if (!selectedFile) {
      setStatusMessage('Please select a file to upload.');
      return;
    }

    setStatusMessage('Uploading...');
    const formData = new FormData();
    formData.append('file', selectedFile);

    fetch(`${API_HOST}/api/upload`, {
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
              <li key={index} onClick={() => handleItemClick(item)}>
                {item.endsWith('/') ? '📁' : '📄'} {item}
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
      </main>
    </div>
  );
}

export default App;
