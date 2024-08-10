import socket
import struct
import os
import hashlib
from tqdm import tqdm
import tkinter as tk
from tkinter import messagebox, font

GROUPS = {
    'Group 1': '224.1.1.1',
    'Group 2': '224.1.1.2',
    'Group 3': '224.1.1.3',
    'Group 4': '224.1.1.4',
    'Group 5': '224.1.1.5'
}
SERVER_PORT = 5002
BUFFER_SIZE = 1024


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
        exit()

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
            # Update the reassembly progress bar
            reassemble_bar.update(1)

    reassemble_bar.close()

    print(f"[+] File {filename} received successfully.")
    sock.close()


def create_gui():
    root = tk.Tk()
    root.title("File Receiver")
    root.geometry("350x200")

    custom_font = font.Font(family="Helvetica", size=12)

    group_frame = tk.Frame(root, padx=10, pady=10)
    group_frame.pack(pady=10)

    tk.Label(group_frame, text="Select Group to Join:", font=custom_font).pack()

    group_options = list(GROUPS.keys())
    group_options.append("Select a group")

    selected_group_var = tk.StringVar(value="Select a group")

    group_menu = tk.OptionMenu(group_frame, selected_group_var, *group_options)
    group_menu.config(font=custom_font, width=20)
    group_menu.pack(pady=5)

    def start_receiving():
        selected_group = selected_group_var.get()
        if selected_group == "Select a group":
            messagebox.showwarning("No Group Selected", "Please select a group to join.")
            return

        multicast_group = GROUPS[selected_group]
        root.destroy()
        receive_file(multicast_group)

    button_frame = tk.Frame(root, padx=10, pady=10)
    button_frame.pack(pady=10)

    receive_btn = tk.Button(button_frame, text="Join Group", font=custom_font, command=start_receiving)
    receive_btn.pack()

    root.mainloop()


if __name__ == "__main__":
    create_gui()
