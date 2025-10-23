#!/usr/bin/env python3
"""
Monitor UDP traffic using scapy (packet sniffing without raw sockets)
Monitors traffic to/from io7t.ddns.net:1024
"""
import sys

try:
    from scapy.all import sniff, UDP, IP
    from datetime import datetime
except ImportError:
    print("ERROR: scapy is not installed.")
    print("Install it with: pip install scapy")
    sys.exit(1)

RADIO_IP = "93.44.225.156"  # io7t.ddns.net resolved
RADIO_PORT = 1024

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

packet_count = 0

def packet_handler(pkt):
    """Handle captured packets"""
    global packet_count

    # Check if it's UDP and involves our radio
    if not pkt.haslayer(UDP):
        return

    if not pkt.haslayer(IP):
        return

    ip_layer = pkt[IP]
    udp_layer = pkt[UDP]

    # Filter for traffic to/from radio on port 1024
    is_to_radio = (ip_layer.dst == RADIO_IP and udp_layer.dport == RADIO_PORT)
    is_from_radio = (ip_layer.src == RADIO_IP and udp_layer.sport == RADIO_PORT)

    if not (is_to_radio or is_from_radio):
        return

    packet_count += 1
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    # Get payload
    if pkt.haslayer('Raw'):
        payload = bytes(pkt['Raw'])
    else:
        payload = b''

    # Direction
    if is_to_radio:
        direction = f"→ TO RADIO"
        src_addr = f"{ip_layer.src}:{udp_layer.sport}"
        dst_addr = f"{ip_layer.dst}:{udp_layer.dport}"
    else:
        direction = f"← FROM RADIO"
        src_addr = f"{ip_layer.src}:{udp_layer.sport}"
        dst_addr = f"{ip_layer.dst}:{udp_layer.dport}"

    # Print packet info
    print(f"\n[{timestamp}] Packet #{packet_count} {direction}")
    print(f"From: {src_addr}")
    print(f"To:   {dst_addr}")
    print(f"Size: {len(payload)} bytes")

    # Identify packet type
    if len(payload) >= 3:
        if payload[0:2] == b'\xef\xfe':
            if payload[2] == 0x02:
                ptype = "DISCOVERY REQUEST" if len(payload) == 63 else "DISCOVERY RESPONSE"
            elif payload[2] == 0x04:
                ptype = "SET IP ADDRESS"
            else:
                ptype = f"HPSDR (cmd={payload[2]:02x})"
        elif payload[0:4] == b'\x00\x00\x00\x00':
            ptype = "UNKNOWN/DATA (starts with zeros)"
        elif payload[0:2] == b'\xef\xfe':
            ptype = f"HPSDR (sync={payload[0]:02x}{payload[1]:02x})"
        else:
            ptype = "UNKNOWN"

        print(f"Type: {ptype}")

    # Print hex dump
    if payload:
        print("Hex dump:")
        print(format_hex_dump(payload))

    print("-" * 80)

def main():
    print("=" * 80)
    print("HPSDR Traffic Monitor")
    print("=" * 80)
    print(f"Monitoring traffic to/from {RADIO_IP}:{RADIO_PORT}")
    print(f"Press Ctrl+C to stop...")
    print("=" * 80)
    print("")

    try:
        # Sniff packets
        # filter: UDP traffic to/from radio IP and port 1024
        sniff(
            filter=f"udp and ((host {RADIO_IP} and port {RADIO_PORT}))",
            prn=packet_handler,
            store=0  # Don't store packets in memory
        )
    except KeyboardInterrupt:
        print(f"\n\n{'=' * 80}")
        print(f"Captured {packet_count} packets total.")
        print("=" * 80)
        print("Exiting...")
    except PermissionError:
        print("\nERROR: Permission denied. Packet sniffing requires root privileges.")
        print("Run with: sudo python3 traffic_monitor.py")
        sys.exit(1)

if __name__ == '__main__':
    main()
