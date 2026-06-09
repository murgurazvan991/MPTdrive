# 1. Use an official, lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy your app scripts and config into the container
COPY server.py api_server.py protocol.py crypto_lib.py config.py archive_utils.py .
COPY var/SAVE_DIR.py ./var/SAVE_DIR.py

# 5. Create the folder where files will be saved
RUN mkdir -p /data

# 6. Expose the port the storage server listens on
EXPOSE 8080

# 7. Default command for this image can be overridden by docker-compose
CMD ["python", "server.py"]
