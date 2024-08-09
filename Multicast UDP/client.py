import socket
import struct
import os
import hashlib

# Multicast group details
MULTICAST_GROUP = '224.1.1.1'
SERVER_PORT = 5001
BUFFER_SIZE = 1024

# Create the UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

# Allow multiple sockets to use the same PORT number
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind to the server address
sock.bind(('', SERVER_PORT))

# Tell the operating system to add the socket to the multicast group
# on all interfaces.
mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

# Receive the file metadata first
data, address = sock.recvfrom(4096)

# Safely decode the metadata
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

# Proceed with receiving the file data as usual
received_packets = {}
total_bytes_received = 0

while total_bytes_received < filesize:
    data, address = sock.recvfrom(BUFFER_SIZE + 36)  # 4 bytes for sequence number, 32 bytes for checksum
    seq_number = struct.unpack('I', data[:4])[0]
    checksum_received = data[4:36].decode()
    file_data = data[36:]

    # Verify checksum
    checksum_calculated = hashlib.md5(file_data).hexdigest()
    if checksum_received == checksum_calculated:
        received_packets[seq_number] = file_data
        total_bytes_received += len(file_data)

        # Send ACK for the received packet
        ack_packet = struct.pack('I', seq_number)
        sock.sendto(ack_packet, address)

# Reassemble the file
with open(filename, 'wb') as f:
    for seq_num in sorted(received_packets.keys()):
        f.write(received_packets[seq_num])

print(f"[+] File {filename} received successfully.")
sock.close()
