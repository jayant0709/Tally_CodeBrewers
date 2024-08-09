import socket
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from tqdm import tqdm

# Constants
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

# Hide the main tkinter window
Tk().withdraw()

# Open the file dialog and let the user select a file
filename = askopenfilename(title="Select a file to send")
if not filename:
    print("No file selected. Exiting.")
    exit()

filesize = os.path.getsize(filename)  # Get the size of the selected file

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(5)
print(f"[*] Listening on {SERVER_HOST}:{SERVER_PORT}")

client_socket, address = server_socket.accept()
print(f"[+] {address} is connected.")

# Send the filename and filesize
client_socket.send(f"{filename}{SEPARATOR}{filesize}".encode())

# Progress bar setup
progress = tqdm(range(filesize), f"Sending {os.path.basename(filename)}", unit="B", unit_scale=True, unit_divisor=1024)

# Open and send the file
with open(filename, "rb") as f:
    while True:
        bytes_read = f.read(BUFFER_SIZE)
        if not bytes_read:
            break
        client_socket.sendall(bytes_read)
        progress.update(len(bytes_read))

# Close the progress bar
progress.close()

print(f"[+] File {filename} sent successfully.")
client_socket.close()
server_socket.close()
