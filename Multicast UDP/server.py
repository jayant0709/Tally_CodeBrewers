import socket
import os
import struct
import hashlib
import time
import threading

# Multicast group details
MULTICAST_GROUP = '224.1.1.1'
SERVER_PORT = 5002
BUFFER_SIZE = 1024
TTL = 1  # Time-to-live for multicast packets

# Retransmission settings
ACK_TIMEOUT = 1  # Time to wait for an acknowledgment before retransmitting
WINDOW_SIZE = 5    # Number of packets sent before waiting for ACKs

# Create the UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, TTL)
sock.settimeout(ACK_TIMEOUT)

# File to send
# filename = "E://Projects//Tally Hackathon//WizardofSystemProgramming.pdf"
filename = "E://TY//BIDA//Lab//Assignment 2//Reference Video.mp4"
filesize = os.path.getsize(filename)

# Send the file details first
file_info = f"{filename}<SEPARATOR>{filesize}"
sock.sendto(file_info.encode('utf-8'), (MULTICAST_GROUP, SERVER_PORT))

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
                sock.sendto(packet, (MULTICAST_GROUP, SERVER_PORT))

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
                    sock.sendto(packet, (MULTICAST_GROUP, SERVER_PORT))

            if not bytes_read:
                break

    print(f"[+] File {filename} sent successfully.")
    sock.close()

threading.Thread(target=send_packets).start()
