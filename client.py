import socket
import os
from tqdm import tqdm

# Constants
SERVER_HOST = '192.168.39.85'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

# Create a socket instance
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
client_socket.connect((SERVER_HOST, SERVER_PORT))

# Receive the filename and filesize from the server
received = client_socket.recv(BUFFER_SIZE).decode()
filename, filesize = received.split(SEPARATOR)
filename = os.path.basename(filename)
filesize = int(filesize)

# Initialize the progress bar
progress = tqdm(range(filesize), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=1024)

# Open the file for writing in binary mode
with open(filename, "wb") as f:
    while True:
        # Read the bytes from the socket
        bytes_read = client_socket.recv(BUFFER_SIZE)
        if not bytes_read:
            break
        # Write the received bytes to the file
        f.write(bytes_read)
        # Update the progress bar
        progress.update(len(bytes_read))

# Close the progress bar and the socket
progress.close()
print(f"[+] File {filename} received successfully.")
client_socket.close()
