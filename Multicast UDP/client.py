import socket
import struct
import os
import hashlib
from tqdm import tqdm
import tkinter as tk
from tkinter import messagebox, font
import mysql.connector

SERVER_PORT = 5002
BUFFER_SIZE = 1024

def connect_to_database():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",  # Replace with your MySQL username
            password="Jayantpatil@07",  # Replace with your MySQL password
            database="FileSharingDB"  # Replace with your MySQL database name
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def fetch_groups():
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT group_name, group_address FROM GroupDetails")
        groups = cursor.fetchall()
        connection.close()
        return {group[0]: group[1] for group in groups}
    return {}

def receive_file(multicast_group):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', SERVER_PORT))

    port_number = sock.getsockname()[1]
    print(f"[+] Connected to port: {port_number}")

    mreq = struct.pack("4sl", socket.inet_aton(multicast_group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    data, address = sock.recvfrom(1024)

    try:
        metadata = data.decode('utf-8')
        filename, filesize = metadata.split('<SEPARATOR>')
        filesize = int(filesize)
        filename = os.path.basename(filename)
    except UnicodeDecodeError as e:
        print("[-] Error: Received data is not valid metadata.")
        sock.close()
        return

    print(f"[+] Receiving file: {filename} with size: {filesize} bytes")

    received_packets = {}
    total_bytes_received = 0

    progress_bar = tqdm(total=filesize, unit='B', unit_scale=True, desc="Receiving")

    while total_bytes_received < filesize:
        data, address = sock.recvfrom(BUFFER_SIZE + 36)
        seq_number = struct.unpack('I', data[:4])[0]
        checksum_received = data[4:36].decode()
        file_data = data[36:]

        checksum_calculated = hashlib.md5(file_data).hexdigest()
        if checksum_received == checksum_calculated:
            received_packets[seq_number] = file_data
            total_bytes_received += len(file_data)

            progress_bar.update(len(file_data))

            ack_packet = struct.pack('I', seq_number)
            sock.sendto(ack_packet, address)

    progress_bar.close()

    reassemble_bar = tqdm(total=len(received_packets), unit='packet', desc="Reassembling")

    with open(filename, 'wb') as f:
        for seq_num in sorted(received_packets.keys()):
            f.write(received_packets[seq_num])
            reassemble_bar.update(1)

    reassemble_bar.close()

    print(f"[+] File {filename} received successfully.")

    # Wait for post-transfer command
    try:
        command_data, address = sock.recvfrom(4096)
        command_metadata = command_data.decode('utf-8')
        if command_metadata.startswith("COMMAND<SEPARATOR>"):
            command = command_metadata.split('<SEPARATOR>')[1]
            print(f"[+] Executing post-transfer command: {command}")
            os.system(command)
    except UnicodeDecodeError as e:
        print("[-] Error: Received data is not a valid command.")
    except Exception as e:
        print(f"[-] Error executing command: {e}")

    sock.close()

def create_gui():
    root = tk.Tk()
    root.title("File Receiver")
    root.geometry("300x200")

    # Define a custom font
    custom_font = font.Font(family="Helvetica", size=12)

    # Create a frame for the group selection
    group_frame = tk.Frame(root, padx=10, pady=10)
    group_frame.pack(pady=10)

    tk.Label(group_frame, text="Select Group:", font=custom_font).pack()

    # Fetch groups from the database
    groups = fetch_groups()
    if not groups:
        messagebox.showerror("Error", "Unable to fetch group details from the database.")
        root.destroy()
        return

    # Define the list of groups for the dropdown menu
    group_options = list(groups.keys())
    group_options.append("Select a group")  # Placeholder for default value

    selected_group_var = tk.StringVar(value="Select a group")  # Set default value

    # Create the OptionMenu widget
    group_menu = tk.OptionMenu(group_frame, selected_group_var, *group_options)
    group_menu.config(font=custom_font, width=20)
    group_menu.pack(pady=5)

    # Create a button to start receiving files
    receive_btn = tk.Button(root, text="Receive File", font=custom_font,
                            command=lambda: start_receiving(selected_group_var.get(), groups))
    receive_btn.pack(pady=20)

    root.mainloop()

def start_receiving(selected_group, groups):
    if not selected_group or selected_group == "Select a group":
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    group_ip = groups[selected_group]
    receive_file(group_ip)

if __name__ == "__main__":
    create_gui()
