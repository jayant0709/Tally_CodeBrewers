import socket
import os
from tqdm import tqdm

# Constants
SERVER_HOST = '192.168.39.85'
# SERVER_HOST = '192.168.0.100'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

# Create a socket instance
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    # Connect to the server
    client_socket.connect((SERVER_HOST, SERVER_PORT))

    # Receive the number of files first
    num_files = int(client_socket.recv(BUFFER_SIZE).decode())

    for _ in range(num_files):
        # Receive the filename and filesize from the server
        received = client_socket.recv(BUFFER_SIZE).decode()
        filename, filesize = received.split(SEPARATOR)
        filename = os.path.basename(filename)
        filesize = int(filesize)

        # Send acknowledgment to the server
        client_socket.send("ACK".encode())

        # Initialize the progress bar
        progress = tqdm(range(filesize), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=1024)

        # Open the file for writing in binary mode
        with open(filename, "wb") as f:
            total_bytes_received = 0
            while total_bytes_received < filesize:
                bytes_read = client_socket.recv(BUFFER_SIZE)
                if not bytes_read:
                    break
                f.write(bytes_read)
                total_bytes_received += len(bytes_read)
                progress.update(len(bytes_read))

        progress.close()
        print(f"[+] File {filename} received successfully.")
except Exception as e:
    print(f"[-] Error: {str(e)}")
finally:
    client_socket.close()
