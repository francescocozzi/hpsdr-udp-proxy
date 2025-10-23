#!/usr/bin/env python3
"""
Simple UDP packet sniffer for HPSDR protocol analysis
Captures UDP packets on port 1024 and saves hex dumps
"""
import socket
import sys
from datetime import datetime

def format_hex_dump(data: bytes, bytes_per_line: int = 16) -> str:
    """Format bytes as hex dump with ASCII representation"""
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i + bytes_per_line]

        # Hex representation
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        hex_part = hex_part.ljust(bytes_per_line * 3 - 1)

        # ASCII representation
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)

        lines.append(f"  {i:04x}  {hex_part}  |{ascii_part}|")

    return '\n'.join(lines)

def main():
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to port 1024 on all interfaces
    try:
        sock.bind(('0.0.0.0', 1024))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Listening on 0.0.0.0:1024")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for HPSDR packets...")
        print("=" * 80)
    except PermissionError:
        print("ERROR: Permission denied. Port 1024 requires root privileges.")
        print("Run with: sudo python3 packet_sniffer.py")
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: Cannot bind to port 1024: {e}")
        print("Make sure no other process is using port 1024")
        sys.exit(1)

    packet_count = 0

    try:
        while True:
            # Receive packet
            data, addr = sock.recvfrom(2048)
            packet_count += 1

            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

            # Print packet info
            print(f"\n[{timestamp}] Packet #{packet_count}")
            print(f"From: {addr[0]}:{addr[1]}")
            print(f"Size: {len(data)} bytes")

            # Identify packet type
            if len(data) >= 3:
                if data[0:2] == b'\xef\xfe':
                    if data[2] == 0x02:
                        ptype = "DISCOVERY REQUEST" if len(data) == 63 else "DISCOVERY RESPONSE"
                    elif data[2] == 0x04:
                        ptype = "SET IP ADDRESS"
                    else:
                        ptype = f"HPSDR (cmd={data[2]:02x})"
                elif data[0:4] == b'\x00\x00\x00\x00':
                    ptype = "UNKNOWN/DATA (starts with zeros)"
                else:
                    ptype = "UNKNOWN"

                print(f"Type: {ptype}")

            # Print hex dump
            print("Hex dump:")
            print(format_hex_dump(data))
            print("-" * 80)

    except KeyboardInterrupt:
        print(f"\n\nCaptured {packet_count} packets total.")
        print("Exiting...")
        sock.close()

if __name__ == '__main__':
    main()
