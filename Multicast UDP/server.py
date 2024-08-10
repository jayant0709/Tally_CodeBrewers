import socket
import os
import struct
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font

# Multicast group details
GROUPS = {
    'Group 1': '224.1.1.1',
    'Group 2': '224.1.1.2',
    'Group 3': '224.1.1.3',
    'Group 4': '224.1.1.4',
    'Group 5': '224.1.1.5'
}
SERVER_PORT = 5002
BUFFER_SIZE = 1024
TTL = 1  # Time-to-live for multicast packets

# Retransmission settings
ACK_TIMEOUT = 1  # Time to wait for an acknowledgment before retransmitting
WINDOW_SIZE = 5  # Number of packets sent before waiting for ACKs


def send_file(filename, group_ip):
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

        print(f"[+] File {filename} sent successfully to {group_ip}.")
        sock.close()

    threading.Thread(target=send_packets).start()


def start_sending(selected_files, selected_group):
    if not selected_files:
        messagebox.showwarning("No Files Selected", "Please select at least one file.")
        return

    if not selected_group:
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    group_ip = GROUPS[selected_group]
    for file in selected_files:
        send_file(file, group_ip)


def open_file_dialog():
    files = filedialog.askopenfilenames(title="Select Files")
    return files


def create_gui():
    root = tk.Tk()
    root.title("File Sharing System")
    root.geometry("400x300")  # Set the window size

    # Define a custom font
    custom_font = font.Font(family="Helvetica", size=12)

    # Create a frame for the file selection
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

    # Create a frame for the group selection
    group_frame = tk.Frame(root, padx=10, pady=10)
    group_frame.pack(pady=10)

    tk.Label(group_frame, text="Select Group:", font=custom_font).pack()

    # Define the list of groups for the dropdown menu
    group_options = list(GROUPS.keys())
    group_options.append("Select a group")  # Placeholder for default value

    selected_group_var = tk.StringVar(value="Select a group")  # Set default value

    # Create the OptionMenu widget
    group_menu = tk.OptionMenu(group_frame, selected_group_var, *group_options)
    group_menu.config(font=custom_font, width=20)
    group_menu.pack(pady=5)

    # Create a button frame to organize buttons
    button_frame = tk.Frame(root, padx=10, pady=10)
    button_frame.pack(pady=10)

    send_btn = tk.Button(button_frame, text="Send Files", font=custom_font, command=lambda: start_sending(selected_files, selected_group_var.get()))
    send_btn.pack()

    root.mainloop()

if __name__ == "__main__":
    create_gui()
