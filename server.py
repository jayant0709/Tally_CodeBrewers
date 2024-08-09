import socket
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilenames
from tqdm import tqdm

# Constants
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

# Hide the main tkinter window
Tk().withdraw()

# Open the file dialog and let the user select multiple files
filenames = askopenfilenames(title="Select files to send")
if not filenames:
    print("No files selected. Exiting.")
    exit()

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(5)
print(f"[*] Listening on {SERVER_HOST}:{SERVER_PORT}")

client_socket, address = server_socket.accept()
print(f"[+] {address} is connected.")

try:
    # Send the number of files first
    client_socket.send(f"{len(filenames)}".encode())

    for filename in filenames:
        filesize = os.path.getsize(filename)

        # Send the filename and filesize
        client_socket.send(f"{filename}{SEPARATOR}{filesize}".encode())

        # Wait for the client to acknowledge receipt of file details
        client_socket.recv(BUFFER_SIZE)

        # Initialize the progress bar
        progress = tqdm(range(filesize), f"Sending {os.path.basename(filename)}", unit="B", unit_scale=True,
                        unit_divisor=1024)

        # Open the file and send its contents
        with open(filename, "rb") as f:
            while True:
                bytes_read = f.read(BUFFER_SIZE)
                if not bytes_read:
                    break
                client_socket.sendall(bytes_read)
                progress.update(len(bytes_read))

        progress.close()
        print(f"[+] {filename} sent successfully.")

    print("[+] All files sent successfully.")
except Exception as e:
    print(f"[-] Error: {str(e)}")
finally:
    client_socket.close()
    server_socket.close()
