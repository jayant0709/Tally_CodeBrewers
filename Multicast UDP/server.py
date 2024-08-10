import socket
import os
import struct
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, font
import mysql.connector

# Database connection
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

# Server and networking settings
SERVER_PORT = 5002
BUFFER_SIZE = 1024
TTL = 1  # Time-to-live for multicast packets
ACK_TIMEOUT = 1  # Time to wait for an acknowledgment before retransmitting
WINDOW_SIZE = 5  # Number of packets sent before waiting for ACKs

def send_file(filename, group_ip, post_transfer_command=None):
    filesize = os.path.getsize(filename)

    # Create the UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, TTL)
    sock.settimeout(ACK_TIMEOUT)

    # Send the file details first
    file_info = f"{os.path.basename(filename)}<SEPARATOR>{filesize}"
    sock.sendto(file_info.encode('utf-8'), (group_ip, SERVER_PORT))

    # Sending thread
    def send_packets():
        sequence_number = 0
        sent_packets = {}

        with open(filename, 'rb') as f:
            while True:
                window_packets = []
                for _ in range(WINDOW_SIZE):
                    bytes_read = f.read(BUFFER_SIZE)
                    if not bytes_read:
                        break

                    checksum = hashlib.md5(bytes_read).hexdigest()
                    packet = struct.pack('I', sequence_number) + checksum.encode() + bytes_read
                    sent_packets[sequence_number] = packet
                    window_packets.append(packet)
                    sequence_number += 1

                # Send packets in the current window
                for packet in window_packets:
                    sock.sendto(packet, (group_ip, SERVER_PORT))

                # Wait for ACKs and handle retransmissions
                for packet in window_packets:
                    seq_num = struct.unpack('I', packet[:4])[0]
                    try:
                        ack, _ = sock.recvfrom(8)
                        ack_num = struct.unpack('I', ack[:4])[0]
                        if ack_num in sent_packets:
                            del sent_packets[ack_num]
                    except socket.timeout:
                        print(f"[-] No ACK for packet {seq_num}, retransmitting...")
                        sock.sendto(packet, (group_ip, SERVER_PORT))

                if not bytes_read:
                    break

        # Send post-transfer command if provided
        if post_transfer_command:
            command_info = f"COMMAND<SEPARATOR>{post_transfer_command}"
            sock.sendto(command_info.encode('utf-8'), (group_ip, SERVER_PORT))

        print(f"[+] File {filename} sent successfully to {group_ip}.")
        sock.close()

    threading.Thread(target=send_packets).start()

def start_sending(selected_files, selected_group, post_transfer_command):
    if not selected_files:
        messagebox.showwarning("No Files Selected", "Please select at least one file.")
        return

    if selected_group == "Select a group":
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT group_address FROM GroupDetails WHERE group_name = %s", (selected_group,))
        result = cursor.fetchone()
        if result:
            group_ip = result[0]
            for file in selected_files:
                send_file(file, group_ip, post_transfer_command)
        else:
            messagebox.showerror("Error", "Selected group not found in the database.")
        connection.close()

def open_file_dialog():
    files = filedialog.askopenfilenames(title="Select Files")
    return files

def create_new_group():
    group_name = simpledialog.askstring("Input", "Enter group name:")
    group_address = simpledialog.askstring("Input", "Enter group address (e.g., 224.1.1.6):")
    if group_name and group_address:
        connection = connect_to_database()
        if connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO GroupDetails (group_name, group_address) VALUES (%s, %s)",
                           (group_name, group_address))
            connection.commit()
            connection.close()
            update_group_menu()  # Refresh the dropdown menu
            messagebox.showinfo("Success", "Group created successfully!")
    else:
        messagebox.showwarning("Input Error", "Please enter both group name and address.")

def update_group_menu():
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT group_name FROM GroupDetails")
        groups = cursor.fetchall()
        group_menu['menu'].delete(0, 'end')
        for group in groups:
            group_menu['menu'].add_command(label=group[0], command=tk._setit(selected_group_var, group[0]))
        connection.close()

def create_gui():
    global group_menu  # Declare as global to use in update_group_menu()
    global selected_group_var  # Declare as global to use in update_group_menu()

    root = tk.Tk()
    root.title("File Sharing System")
    root.geometry("500x500")  # Increased window size to accommodate new options

    custom_font = font.Font(family="Helvetica", size=12)

    # File selection frame
    file_frame = tk.Frame(root, padx=10, pady=10)
    file_frame.pack(pady=10)

    tk.Label(file_frame, text="Select Files:", font=custom_font).pack()

    selected_files = []

    def select_files():
        nonlocal selected_files
        selected_files = open_file_dialog()
        selected_files_label.config(text="\n".join(selected_files))

    selected_files_label = tk.Label(file_frame, text="", font=custom_font)
    selected_files_label.pack()

    select_files_btn = tk.Button(file_frame, text="Browse Files", font=custom_font, command=select_files)
    select_files_btn.pack(pady=(5, 0))

    # Group management frame
    group_frame = tk.Frame(root, padx=10, pady=10)
    group_frame.pack(pady=10)

    tk.Label(group_frame, text="Select Group:", font=custom_font).pack()

    selected_group_var = tk.StringVar(value="Select a group")

    group_menu = tk.OptionMenu(group_frame, selected_group_var, "Loading...")  # Placeholder
    group_menu.config(font=custom_font, width=20)
    group_menu.pack(pady=5)

    create_group_btn = tk.Button(group_frame, text="Create New Group", font=custom_font, command=create_new_group)
    create_group_btn.pack(pady=5)

    update_group_menu()  # Initial call to populate the dropdown

    # Post-transfer command frame
    command_frame = tk.Frame(root, padx=10, pady=10)
    command_frame.pack(pady=10)

    tk.Label(command_frame, text="Post-Transfer Command:", font=custom_font).pack()
    command_entry = tk.Entry(command_frame, font=custom_font, width=40)
    command_entry.pack(pady=5)

    # Button to start sending files
    send_btn = tk.Button(root, text="Send Files", font=custom_font,
                         command=lambda: start_sending(selected_files, selected_group_var.get(), command_entry.get()))
    send_btn.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
