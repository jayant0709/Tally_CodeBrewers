import socket
import os
import struct
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, font
import mysql.connector
import uuid
import tqdm
import time
from datetime import datetime, timedelta

# Server and networking settings
SERVER_PORT = 5002
BUFFER_SIZE = 1024
TTL = 1  # Time-to-live for multicast packets
ACK_TIMEOUT = 1  # Time to wait for an acknowledgment before retransmitting
WINDOW_SIZE = 5  # Number of packets sent before waiting for ACKs


# Database connection
def connect_to_database():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",  # Replace with your MySQL username
            password="manglesh2004",  # Replace with your MySQL password
            database="FileSharingDB"  # Replace with your MySQL database name
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None


def send_file_to_client(sock, packet, group_ip):
    sock.sendto(packet, (group_ip, SERVER_PORT))


# Function to create a table for a new group
def create_group_table(group_name):
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        try:
            table_name = f"{group_name.replace(' ', '_')}_users"
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (user_id VARCHAR(255) PRIMARY KEY)")
            connection.commit()
            print(f"Table '{table_name}' created or already exists.")
        except mysql.connector.Error as err:
            print(f"Failed to create table '{table_name}': {err}")
        finally:
            connection.close()


# Fetch groups from the database
def fetch_groups():
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT group_name, group_address FROM GroupDetails")
        groups = cursor.fetchall()
        connection.close()
        return {group[0]: group[1] for group in groups}
    return {}


# Function to add a user to the group table
def add_user_to_group(user_id, group_name):
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        insert_query = f"INSERT INTO {group_name.replace(' ', '_')}_users (user_id) VALUES (%s)"
        cursor.execute(insert_query, (user_id,))
        connection.commit()
        connection.close()


# Function to check if a user_id is valid for a group
def is_user_id_valid(user_id, group_name):
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        check_query = f"SELECT COUNT(*) FROM {group_name.replace(' ', '_')}_users WHERE user_id = %s"
        cursor.execute(check_query, (user_id,))
        result = cursor.fetchone()[0]
        connection.close()
        return result > 0
    return False


def handle_user_requests():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # sock.bind(('0.0.0.0', SERVER_PORT))
    sock.bind(('0.0.0.0', 5001))

    while True:
        try:
            data, address = sock.recvfrom(1024)
            request = data.decode('utf-8')
            username = ""
            received_list = []
            received_list = request.split(':')
            action = ""
            group_name = ""
            # action, username, group_name = request.split(':')
            if (len(received_list) == 3):
                action = received_list[0]
                username = received_list[1]
                group_name = received_list[2]
            else:
                action = received_list[0]
                group_name = received_list[1]

            # print(action)
            # print(username)
            # print(group_name)

            if action == "JOIN":
                # Simulate approval process (you can add more logic here)
                approve = messagebox.askyesno("Group Join Request",
                                              f"Approve user '{username}' to join '{group_name}'?")

                if approve:
                    create_group_table(group_name)  # Ensure the group's table exists
                    user_id = str(uuid.uuid4())
                    add_user_to_group(user_id, group_name)
                    response = f"APPROVED:{user_id}"
                    add_active_user(user_id, group_name)
                    # send_previous_files(group_name, user_id)
                else:
                    response = "DENIED"

                sock.sendto(response.encode('utf-8'), address)

            elif action == "VALIDATE":
                user_id = username
                group_name = group_name
                if is_user_id_valid(user_id, group_name):
                    response = "VALID"
                    add_active_user(user_id, group_name)
                    # send_previous_files(group_name, user_id)
                else:
                    response = "INVALID"
                sock.sendto(response.encode('utf-8'), address)

            elif action == "UPDATE":
                user_id = username
                group_name = group_name
                # response = ""
                if update_required(group_name, user_id):
                    response = "UPDATE NEEDED"
                else:
                    response = "UPDATED"

                sock.sendto(response.encode('utf-8'), address)
                time.sleep(1)
                send_previous_files(group_name, user_id)

        except Exception as e:
            print(f"Error occurred: {e}")


def add_active_user(user_id, group_name):
    path = f"./{group_name.replace(' ', '_')}_active_users.txt"
    present = False

    if os.path.exists(path):
        with open(path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if user_id == line.strip():
                    present = True
                    break

    if not present:
        with open(path, 'a') as f:
            f.write(user_id + "\n")


def send_file(filename, group_ip, user_ids, post_transfer_command=None):
    filesize = os.path.getsize(filename)
    num_packets = (filesize + BUFFER_SIZE - 1)  # BUFFER SIZE

    # Create the UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, TTL)
    sock.settimeout(ACK_TIMEOUT)

    # Paths to save the acknowledgment file and files sent file in the current working directory
    ack_file_path = os.path.join(os.getcwd(), f"{filename}_acknowledgments.txt")

    # Create acknowledgment and files sent files if they don't exist
    if not os.path.exists(ack_file_path):
        with open(ack_file_path, 'w') as ack_file:
            ack_file.write("")

    # Check existing acknowledgments to avoid resending the file
    with open(ack_file_path, 'r') as ack_file:
        acknowledged_users = set(line.strip() for line in ack_file.readlines()[1:])

    # Send the file details first
    file_info = f"{os.path.basename(filename)}<SEPARATOR>{filesize}"
    sock.sendto(file_info.encode('utf-8'), (group_ip, SERVER_PORT))

    # Sending thread for each user_id
    def send_packets(user_id):

        if user_id in acknowledged_users:
            print(f"[+] Skipping user {user_id} as the file {filename} has already been acknowledged.")
            return

        sequence_number = 0
        sent_packets = {}
        progress_bar = tqdm.tqdm(total=num_packets, desc=f"Sending {filename} to {user_id}")

        with open(filename, 'rb') as f:
            while True:
                window_packets = []
                for _ in range(WINDOW_SIZE):
                    bytes_read = f.read(BUFFER_SIZE)
                    if not bytes_read:
                        break

                    checksum = hashlib.md5(bytes_read).hexdigest()
                    header = struct.pack('I', sequence_number) + checksum.encode() + user_id.encode().ljust(
                        36)  # Adjust size if necessary
                    packet = header + bytes_read
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
                        ack, _ = sock.recvfrom(44)  # Adjust size if necessary
                        ack_num, ack_user_id = struct.unpack('I', ack[:4])[0], ack[4:].strip().decode()
                        if ack_num in sent_packets and ack_user_id == user_id:
                            del sent_packets[ack_num]
                            progress_bar.update(1)  # Update the progress bar
                    except socket.timeout:
                        print(f"[-] No ACK from {user_id} for packet {seq_num}, retransmitting...")
                        sock.sendto(packet, (group_ip, SERVER_PORT))

                if not bytes_read:
                    break

        progress_bar.close()

        print(f"[+] File {filename} sent successfully to {user_id}.")

        # Listen for final acknowledgment from the client
        try:
            while True:
                ack_data, _ = sock.recvfrom(4096)
                ack_message = ack_data.decode('utf-8')
                if ack_message.startswith("ACK_COMPLETE<SEPARATOR>"):
                    ack_user_id, ack_filename = ack_message.split('<SEPARATOR>')[1:3]
                    if ack_filename == os.path.basename(filename) and ack_user_id == user_id:
                        file = open(ack_file_path, 'r').readlines()
                        file = [f.strip() for f in file]
                        if (ack_user_id not in file):
                            with open(ack_file_path, 'a') as ack_file:
                                ack_file.write(f"{user_id}\n")

                        print(f"[+] Received final acknowledgment from user {user_id} for file {filename}.")
                        break

        except socket.timeout:
            print(f"[-] Timeout while waiting for final acknowledgment from user {user_id}.")
        except Exception as e:
            print(f"[-] Error receiving final acknowledgment: {e}")

    # Start a thread for each user in the group
    for user_id in user_ids:
        threading.Thread(target=send_packets, args=(user_id,)).start()

    # Send post-transfer command if provided
    if post_transfer_command:
        command_info = f"COMMAND<SEPARATOR>{post_transfer_command}"
        sock.sendto(command_info.encode('utf-8'), (group_ip, SERVER_PORT))


def start_sending(selected_files, selected_group, post_transfer_command, schedule_time):
    if not selected_files:
        messagebox.showwarning("No Files Selected", "Please select at least one file.")
        return

    if selected_group == "Select a group":
        messagebox.showwarning("No Group Selected", "Please select a group.")
        return

    # Check if a valid schedule time is set
    if schedule_time:
        now = datetime.now()
        scheduled_datetime = datetime.combine(now.date(), schedule_time)

        if scheduled_datetime < now:
            messagebox.showwarning("Invalid Schedule Time",
                                   "The scheduled time is in the past. File transfer will not execute.")
            return

        delay_seconds = (scheduled_datetime - now).total_seconds()

        if delay_seconds > 0:
            messagebox.showinfo("Scheduled", f"File transfer scheduled to start at {schedule_time}. Waiting...")
            time.sleep(delay_seconds)

    # Proceed with file sending
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT group_address FROM GroupDetails WHERE group_name = %s", (selected_group,))
        result = cursor.fetchone()
        if result:
            group_ip = result[0]

            # Fetch the user_ids of active users in the group
            cursor.execute(f"SELECT user_id FROM {selected_group.replace(' ', '_')}_users")
            user_ids = [row[0] for row in cursor.fetchall()]

            with open(f"{selected_group.replace(' ', '_')}_active_users.txt", 'r') as f:
                active_users = [line.strip() for line in f.readlines()]

            # Compare and filter only the active users who are also in the user_ids list
            send_list = [user for user in active_users if user in user_ids]

            print(send_list)

            if not os.path.exists(f"{selected_group.replace(' ', '_')}_sent_files.txt"):
                with open(f"{selected_group.replace(' ', '_')}_sent_files.txt", 'w') as ack_file:
                    ack_file.write("")

            for file in selected_files:
                with open(f"{selected_group.replace(' ', '_')}_sent_files.txt", 'a') as ack_file:
                    ack_file.write(f"{file}\n")
                send_file(file, group_ip, send_list, post_transfer_command)
        else:
            messagebox.showerror("Error", "Selected group not found in the database.")
        connection.close()


def update_required(group_name, user_id):
    if not os.path.exists(f"{group_name.replace(' ', '_')}_sent_files.txt"):
        return False

    # groups = fetch_groups()
    with open(f"{group_name.replace(' ', '_')}_sent_files.txt", 'r') as f:
        sent_files = f.readlines()
        sent_files = [file.replace("\n", "") for file in sent_files]
        send_file = 0
        for file in sent_files:
            if not os.path.exists(f"{file}_acknowledgments.txt"):
                send_file += 1
                continue

            with open(f"{file}_acknowledgments.txt", 'r') as id:

                ids = id.readlines()
                ids = [i.strip() for i in ids]

                if user_id not in ids:
                    send_file += 1

        if send_file != 0:
            return True
        else:
            return False


def send_previous_files(group_name, user_id):
    # if not os.path.exists(f"{group_name.replace(' ', '_')}_sent_files.txt"):
    #     return None
    print("Previous files are being sent")
    previous_files = []
    groups = fetch_groups()
    with open(f"{group_name.replace(' ', '_')}_sent_files.txt", 'r') as f:
        sent_files = f.readlines()
        # print(sent_files)
        sent_files = [file.replace("\n", "") for file in sent_files]
        for file in sent_files:

            if not os.path.exists(f"{file}_acknowledgments.txt"):
                previous_files.append(file)
                continue

            with open(f"{file}_acknowledgments.txt", 'r') as id:

                ids = id.readlines()
                ids = [i.strip() for i in ids]
                if user_id not in ids:
                    previous_files.append(file)

    print(previous_files)
    if len(previous_files) > 0:
        for f in previous_files:
            print(f"Sending file {f}")
            # threading.Thread(target=send_file, args=(f, groups[group_name], [user_id])).start()
            send_file(f, groups[group_name], [user_id])


# Function to open the file dialog and select files
def open_file_dialog():
    files = filedialog.askopenfilenames(title="Select Files")
    return files


# Function to create a new group
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
            create_group_table(group_name)
            messagebox.showinfo("Success", "Group created successfully!")
    else:
        messagebox.showwarning("Input Error", "Please enter both group name and address.")


# Function to update the group dropdown menu
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


# Function to create the GUI
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

    # Time scheduling frame
    schedule_frame = tk.Frame(root, padx=10, pady=10)
    schedule_frame.pack(pady=10)

    tk.Label(schedule_frame, text="Set Transfer Start Time (HH:MM:SS):", font=custom_font).pack()

    send_time_set = False  # Local variable to track if the time has been set

    time_frame = tk.Frame(schedule_frame)
    time_frame.pack()

    current_time = datetime.now()
    formatted_time = current_time.strftime("%H:%M:%S")

    hour_var = tk.StringVar(value=formatted_time.split(":")[0])
    min_var = tk.StringVar(value=formatted_time.split(":")[1])
    sec_var = tk.StringVar(value=formatted_time.split(":")[2])

    hour_entry = tk.Entry(time_frame, textvariable=hour_var, width=3, font=custom_font)
    hour_entry.pack(side=tk.LEFT)
    tk.Label(time_frame, text=":", font=custom_font).pack(side=tk.LEFT)

    min_entry = tk.Entry(time_frame, textvariable=min_var, width=3, font=custom_font)
    min_entry.pack(side=tk.LEFT)
    tk.Label(time_frame, text=":", font=custom_font).pack(side=tk.LEFT)

    sec_entry = tk.Entry(time_frame, textvariable=sec_var, width=3, font=custom_font)
    sec_entry.pack(side=tk.LEFT)

    def set_time():
        nonlocal send_time_set
        send_time_set = True
        messagebox.showinfo("Time Set", "Send time has been set.")
        return send_time_set

    set_send_time = tk.Button(time_frame, text="Set Send Time", font=custom_font, command=set_time)
    set_send_time.pack(pady=5)

    def get_schedule_time():
        try:
            if send_time_set:
                return datetime.strptime(f"{hour_var.get()}:{min_var.get()}:{sec_var.get()}", "%H:%M:%S").time()
            else:
                return None
        except ValueError:
            messagebox.showerror("Invalid Time", "Please enter a valid time.")
            return None

    # Post-transfer command frame
    command_frame = tk.Frame(root, padx=10, pady=10)
    command_frame.pack(pady=10)

    tk.Label(command_frame, text="Post-Transfer Command:", font=custom_font).pack()
    command_entry = tk.Entry(command_frame, font=custom_font, width=40)
    command_entry.pack(pady=5)

    # Progress bar
    progress_frame = tk.Frame(root, padx=10, pady=10)
    progress_frame.pack(pady=10)

    # Button to start sending files
    send_btn = tk.Button(root, text="Send Files", font=custom_font,
                         command=lambda: start_sending(selected_files, selected_group_var.get(), command_entry.get(),
                                                       get_schedule_time()))
    send_btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    threading.Thread(target=handle_user_requests).start()  # Start the thread to handle user requests
    create_gui()
