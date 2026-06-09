# 1. Use an official, lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements and install the encryption library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy your server scripts and config into the container
COPY server.py protocol.py crypto_lib.py config.py archive_utils.py var/SAVE_DIR.py ./
COPY var/ ./var/

# 5. Create the folder where files will be saved
RUN mkdir -p /data

# 6. Expose the port your server listens on
EXPOSE 8080

# 7. Start the server
CMD ["python", "server.py"]