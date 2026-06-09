import base64

# This is your 32-byte (256-bit) master key for AES-GCM encryption.
# It MUST be exactly the same on both the client and the server.
# WARNING: Keep this file completely secret. Never upload it to a public GitHub repo!

# Replace the string below with your own randomly generated key
KEY = base64.b64decode(b'Szlw7Jeoos+e6e40JelHkg6wLRWB/ZH7AfYSBA7rdAg=')