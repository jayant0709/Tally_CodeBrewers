import socket
import os
from tkinter import Tk, Label, Button, Listbox, END, MULTIPLE
from tkinter.filedialog import askopenfilenames
from threading import Thread
from tqdm import tqdm

# Constants
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

clients = {}  # Dictionary to store connected clients

# Function to start the file transfer
def start_file_transfer():
    global clients, filenames

    # Get the selected client IP addresses
    selected_clients = client_listbox.curselection()
    selected_client_ips = [client_listbox.get(i) for i in selected_clients]

    for client_ip in selected_client_ips:
        client_socket = clients[client_ip]

        # Send the number of files first
        client_socket.send(f"{len(filenames)}".encode())

        for filename in filenames:
            filesize = os.path.getsize(filename)

            # Send the filename and filesize
            client_socket.send(f"{filename}{SEPARATOR}{filesize}".encode())

            # Wait for the client to acknowledge receipt of file details
            client_socket.recv(BUFFER_SIZE)

            # Initialize the progress bar
            progress = tqdm(range(filesize), f"Sending {os.path.basename(filename)} to {client_ip}", unit="B", unit_scale=True,
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
            print(f"[+] {filename} sent successfully to {client_ip}.")

        print(f"[+] All files sent successfully to {client_ip}.")
        client_socket.close()

# Function to accept client connections
def accept_clients():
    global server_socket, clients
    while True:
        client_socket, address = server_socket.accept()
        client_ip = address[0]
        print(f"[+] {client_ip} connected.")
        clients[client_ip] = client_socket  # Store the client socket with its IP address

# Function to refresh the client list in the Listbox
def refresh_client_list():
    global clients
    client_listbox.delete(0, END)  # Clear the Listbox
    for client_ip in clients.keys():
        client_listbox.insert(END, client_ip)  # Add each connected client IP to the Listbox

# Create a Tkinter window for file selection and client connection
def create_gui():
    global client_listbox

    root = Tk()
    root.title("File and Client Selector")

    def on_file_select():
        global filenames
        # Open the file dialog and let the user select multiple files
        filenames = askopenfilenames(title="Select files to send")
        if not filenames:
            print("No files selected. Exiting.")
            server_socket.close()
            exit()

        # Enable client listbox, refresh button, and send button after file selection
        client_listbox.config(state='normal')
        refresh_button.config(state='normal')
        send_button.config(state='normal')

    # Create a button to select files
    select_button = Button(root, text="Select Files", command=on_file_select)
    select_button.grid(row=0, column=0, padx=10, pady=10)

    Label(root, text="Select Clients:").grid(row=1, column=0, padx=10, pady=10)

    # Create a Listbox to show connected clients (with MULTIPLE selection mode)
    client_listbox = Listbox(root, state='disabled', selectmode=MULTIPLE)
    client_listbox.grid(row=1, column=1, padx=10, pady=10)

    # Create a refresh button to refresh the client list
    refresh_button = Button(root, text="Refresh Client List", command=refresh_client_list, state='disabled')
    refresh_button.grid(row=2, column=0, padx=10, pady=10)

    send_button = Button(root, text="Send Files", command=start_file_transfer, state='disabled')
    send_button.grid(row=2, column=1, padx=10, pady=10)

    # Start a thread to accept clients
    Thread(target=accept_clients, daemon=True).start()

    root.mainloop()

# Initialize the server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(5)
print(f"[*] Listening on {SERVER_HOST}:{SERVER_PORT}")

create_gui()
