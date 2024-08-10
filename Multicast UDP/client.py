import socket
import struct
import os
import hashlib
from tqdm import tqdm
import tkinter as tk
from tkinter import messagebox, font, simpledialog
import mysql.connector

SERVER_PORT = 5002
BUFFER_SIZE = 1024
SERVER_IP = '192.168.0.101'


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


# Function to send a request to join a group
def send_join_request(group_name):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:

        username = simpledialog.askstring("Input", "Enter your username :")

        request = f"JOIN:{username}:{group_name}"
        # sock.sendto(request.encode('utf-8'), (SERVER_IP, SERVER_PORT))
        sock.sendto(request.encode('utf-8'), (SERVER_IP, 5001))

        # Wait for server response
        response, _ = sock.recvfrom(1024)
        response = response.decode('utf-8')

        if response.startswith("APPROVED"):
            user_id = response.split(":")[1]
            messagebox.showinfo("Join Group", f"Join request approved! Your user ID is {user_id}.")
            save_user_id(group_name, user_id)
            return user_id
        else:
            messagebox.showerror("Join Group", "Join request denied by the server.")
            return None


# Functionality to save the user ID
def save_user_id(group_name, user_id):
    with open(f"{group_name}_user_id.txt", 'w') as f:
        f.write(user_id)


def get_saved_user_id(group_name):
    try:
        with open(f"{group_name}_user_id.txt", 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


# Functionality to validate the user ID
def validate_user_id(user_id, group_name):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    validation_request = f"VALIDATE:{user_id}:{group_name}"
    sock.sendto(validation_request.encode('utf-8'), (SERVER_IP, 5001))

    response, _ = sock.recvfrom(1024)
    response = response.decode('utf-8')
    return response == "VALID"


# Functionality to join the multicast group
def join_multicast_group(user_id, group_name):
    if validate_user_id(user_id, group_name):
        GROUPS = fetch_groups()
        multicast_group = GROUPS[group_name]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', SERVER_PORT))
        # sock.bind(('', 5001))

        mreq = struct.pack("4sl", socket.inet_aton(multicast_group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        print(f"[+] User {user_id} joined multicast group {group_name} ({multicast_group})")
        return sock
    else:
        print("User ID validation failed")
        return None


def receive_file(multicast_group):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', SERVER_PORT))
        # sock.bind(('', 5001))

        port_number = sock.getsockname()[1]
        print(f"[+] Connected to port: {port_number}")

        mreq = struct.pack("4sl", socket.inet_aton(multicast_group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Validation for meta data
        data, address = sock.recvfrom(4096)

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

        # File size check
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

    except PermissionError as e:
        print(f"PermissionError: {e}")
        print("Ensure that the port is not being blocked by a firewall or used by another process.")

    except Exception as e:
        print(f"Error occurred: {e}")


def create_gui():
    root = tk.Tk()
    root.title("File Receiver")
    root.geometry("300x300")  # Increased height to accommodate the new button and username entry

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

    # Create a frame for the username input
    username_frame = tk.Frame(root, padx=10, pady=10)
    username_frame.pack(pady=10)

    # tk.Label(username_frame, text="Enter Username:", font=custom_font).pack()
    # username_entry = tk.Entry(username_frame, font=custom_font)
    # username_entry.pack(pady=5)

    # Create a button to join the group
    join_group_btn = tk.Button(root, text="Join Group", font=custom_font,
                               command=lambda: join_group(selected_group_var.get(), groups))
    join_group_btn.pack(pady=10)

    # Create a button to start receiving files
    receive_btn = tk.Button(root, text="Receive File", font=custom_font,
                            command=lambda: start_receiving(selected_group_var.get(), groups))
    receive_btn.pack(pady=10)

    root.mainloop()


def join_group(selected_group, username):
    if not selected_group or selected_group == "Select a group":
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    group_name = selected_group
    if not username:
        messagebox.showwarning("No Username", "Please enter a username.")
        return

    user_id = get_saved_user_id(group_name)

    if user_id:
        # Validate the existing user ID
        if validate_user_id(user_id, group_name):
            messagebox.showinfo("Validation Successful", f"User ID is valid for group {group_name}.")
        else:
            messagebox.showerror("Validation Failed", "User ID is invalid. Requesting a new one.")
            request_new_user_id(group_name)
    else:
        # No user ID saved, request to join the group
        request_new_user_id(group_name)


def request_new_user_id(group_name):
    user_id = send_join_request(group_name)
    if user_id:
        messagebox.showinfo("Join Successful", f"Joined group {group_name} with User ID: {user_id}.")
    else:
        messagebox.showerror("Join Failed", f"Failed to join group {group_name}.")


def start_receiving(selected_group, groups):
    if not selected_group or selected_group == "Select a group":
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    user_id = get_saved_user_id(selected_group)
    if not user_id or not validate_user_id(user_id, selected_group):
        messagebox.showerror("Not Joined", f"You must join the group {selected_group} before receiving files.")
        return

    # print(groups)
    group_ip = groups[selected_group]
    # print(group_ip)
    receive_file(group_ip)


if __name__ == "__main__":
    create_gui()
