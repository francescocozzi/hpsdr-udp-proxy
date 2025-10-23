"""
HPSDR Protocol Packet Handler

Analyzes and parses HPSDR protocol packets (Protocol 1 and Protocol 2).
Based on OpenHPSDR protocol specification.
"""
import struct
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from ..utils import get_logger


class HPSDRPacketType(Enum):
    """HPSDR packet types"""
    UNKNOWN = 0
    DISCOVERY = 1           # Discovery request/response
    ERASE = 2              # Flash erase command
    PROGRAM = 3            # Programming command
    SET_IP = 4             # Set IP address
    DATA = 5               # I/Q data packet
    START = 6              # Start streaming
    STOP = 7               # Stop streaming
    WIDE_BAND_DATA = 8     # Wideband data (Protocol 2)


@dataclass
class HPSDRPacket:
    """
    Represents a parsed HPSDR packet
    """
    packet_type: HPSDRPacketType
    raw_data: bytes
    sync_bytes: Optional[bytes] = None
    sequence_number: Optional[int] = None
    command_bytes: Optional[bytes] = None
    payload: Optional[bytes] = None

    # Discovery-specific fields
    is_response: bool = False
    mac_address: Optional[str] = None
    board_id: Optional[int] = None
    firmware_version: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def __str__(self):
        return (f"HPSDRPacket(type={self.packet_type.name}, "
                f"size={len(self.raw_data)}, seq={self.sequence_number})")


class PacketHandler:
    """
    HPSDR protocol packet analyzer and parser

    Supports both Protocol 1 (Metis/Hermes) and Protocol 2 (Hermes Lite 2).
    """

    # HPSDR Protocol Constants
    SYNC_PATTERN_1 = b'\xef\xfe'       # Protocol 1 sync
    DISCOVERY_SYNC = b'\xef\xfe'       # Discovery sync

    # Packet sizes
    PROTOCOL_1_SIZE = 1032              # Standard data packet size
    DISCOVERY_REQUEST_SIZE = 63         # Discovery request
    DISCOVERY_RESPONSE_SIZE = 60        # Discovery response

    # Command bytes
    CMD_DATA_IQ = 0x01          # I/Q data streaming
    CMD_DISCOVERY = 0x02        # Discovery request/response
    CMD_SET_IP = 0x04           # Set IP address (triggers streaming)
    CMD_ERASE = 0x03            # Flash erase command (not commonly used)
    CMD_PROGRAM = 0x05          # Programming command (not commonly used)

    def __init__(self):
        """Initialize packet handler"""
        self.logger = get_logger(__name__)
        self.stats = {
            'total_packets': 0,
            'discovery_packets': 0,
            'data_packets': 0,
            'unknown_packets': 0,
            'error_packets': 0,
        }

    def parse(self, data: bytes) -> HPSDRPacket:
        """
        Parse HPSDR packet

        Args:
            data: Raw packet data

        Returns:
            Parsed HPSDRPacket object
        """
        self.stats['total_packets'] += 1

        try:
            # Check for SET_IP packet (must be before discovery as both start with 0xEFFE)
            if self._is_set_ip_packet(data):
                return self._parse_set_ip(data)

            # Check for discovery packet
            elif self._is_discovery_packet(data):
                self.stats['discovery_packets'] += 1
                return self._parse_discovery(data)

            # Check for data packet (Protocol 1)
            elif self._is_protocol1_data(data):
                self.stats['data_packets'] += 1
                return self._parse_protocol1_data(data)

            # Unknown packet type
            else:
                self.stats['unknown_packets'] += 1
                self.logger.debug(f"Unknown packet type, size={len(data)}, "
                                f"header={data[:8].hex() if len(data) >= 8 else data.hex()}")
                return HPSDRPacket(
                    packet_type=HPSDRPacketType.UNKNOWN,
                    raw_data=data
                )

        except Exception as e:
            self.stats['error_packets'] += 1
            self.logger.error(f"Error parsing packet: {e}")
            return HPSDRPacket(
                packet_type=HPSDRPacketType.UNKNOWN,
                raw_data=data,
                metadata={'error': str(e)}
            )

    def _is_set_ip_packet(self, data: bytes) -> bool:
        """
        Check if packet is a SET IP address packet

        SET IP packet format:
        - Bytes 0-1: 0xEFFE (sync)
        - Byte 2: 0x04 (set IP command)
        - Byte 3: Usually 0x01
        - Remaining: IP address and other config
        """
        if len(data) < 3:
            return False

        return (data[0:2] == self.SYNC_PATTERN_1 and
                data[2] == self.CMD_SET_IP)

    def _is_discovery_packet(self, data: bytes) -> bool:
        """
        Check if packet is a discovery packet

        Discovery packet format:
        - Bytes 0-1: 0xEFFE (sync)
        - Byte 2: 0x02 (discovery command)
        - Remaining: depends on request/response
        """
        if len(data) < 3:
            return False

        return (data[0:2] == self.DISCOVERY_SYNC and
                data[2] == self.CMD_DISCOVERY)

    def _is_protocol1_data(self, data: bytes) -> bool:
        """
        Check if packet is Protocol 1 data packet

        Protocol 1 data format:
        - Bytes 0-2: 0xEFFE01 (sync + endpoint)
        - Byte 3-6: Sequence number
        - Remaining: I/Q data and control bytes
        """
        if len(data) < 8:
            return False

        # Check sync pattern and endpoint
        return data[0:2] == self.SYNC_PATTERN_1 and data[2] == 0x01

    def _parse_discovery(self, data: bytes) -> HPSDRPacket:
        """
        Parse discovery packet

        Discovery request (from client):
        - 0-1: 0xEFFE
        - 2: 0x02 (command)
        - 3-62: Padding (typically zeros)

        Discovery response (from radio):
        - 0-1: 0xEFFE
        - 2: 0x02 (command)
        - 3-8: MAC address (6 bytes)
        - 9: Board ID
        - 10-14: Additional info
        - 15+: Device name, firmware version, etc.
        """
        packet = HPSDRPacket(
            packet_type=HPSDRPacketType.DISCOVERY,
            raw_data=data,
            sync_bytes=data[0:2]
        )

        # Determine if this is a request or response
        # Response typically has non-zero MAC address
        if len(data) >= 9:
            mac_bytes = data[3:9]
            if any(b != 0 for b in mac_bytes):
                # This is a response
                packet.is_response = True
                packet.mac_address = ':'.join(f'{b:02x}' for b in mac_bytes)

                if len(data) >= 10:
                    packet.board_id = data[9]

                # Try to extract firmware version if present
                if len(data) >= 15:
                    # Firmware version is typically at specific offset
                    fw_bytes = data[10:15]
                    packet.firmware_version = '.'.join(str(b) for b in fw_bytes if b != 0)

                self.logger.debug(f"Discovery response: MAC={packet.mac_address}, "
                                f"Board ID={packet.board_id}")
            else:
                # This is a request
                packet.is_response = False
                self.logger.debug("Discovery request received")

        return packet

    def _parse_set_ip(self, data: bytes) -> HPSDRPacket:
        """
        Parse SET IP address packet

        SET IP packet format (64 bytes):
        - 0-1: 0xEFFE (sync)
        - 2: 0x04 (SET IP command)
        - 3: 0x01 (subcommand)
        - 4-7: IP address (4 bytes)
        - 8+: Additional configuration

        This packet is sent by the client to configure the radio's
        IP address and triggers the radio to start streaming IQ data.
        """
        packet = HPSDRPacket(
            packet_type=HPSDRPacketType.SET_IP,
            raw_data=data,
            sync_bytes=data[0:2]
        )

        # Extract IP address if present
        if len(data) >= 8:
            ip_bytes = data[4:8]
            ip_address = '.'.join(str(b) for b in ip_bytes)
            packet.metadata['target_ip'] = ip_address
            self.logger.info(f"🔧 SET IP ADDRESS packet: target IP={ip_address}")

        return packet

    def _parse_protocol1_data(self, data: bytes) -> HPSDRPacket:
        """
        Parse Protocol 1 data packet

        Protocol 1 format (1032 bytes total):
        - 0-2: Sync (0xEFFE01)
        - 3-6: Sequence number (4 bytes, big-endian)
        - 7-1031: USB frame data
            - Contains 2 × 512 byte USB frames
            - Each USB frame has control bytes and I/Q samples

        Control bytes (C0-C4) in USB frames contain:
        - Frequency, mode, filters, AGC, etc.
        """
        if len(data) < self.PROTOCOL_1_SIZE:
            self.logger.warning(f"Protocol 1 packet too small: {len(data)} bytes")

        packet = HPSDRPacket(
            packet_type=HPSDRPacketType.DATA,
            raw_data=data,
            sync_bytes=data[0:3]
        )

        # Extract sequence number
        if len(data) >= 7:
            # Sequence number is bytes 3-6 (big-endian 32-bit)
            packet.sequence_number = struct.unpack('>I', data[3:7])[0]

        # Extract USB frame data (512 bytes × 2)
        if len(data) >= 1032:
            # First USB frame: bytes 7-518
            # Second USB frame: bytes 519-1030
            packet.payload = data[7:1031]

            # Extract control bytes from first USB frame
            # C0 is at offset 11 (7 + 4 for sync/header within frame)
            # Control bytes C0-C4 repeat every 512 bytes
            if len(data) >= 16:
                packet.command_bytes = data[11:16]  # C0-C4

                # Parse control byte C0 (contains PTT, frequency changes, etc.)
                c0 = data[11]
                packet.metadata['ptt'] = bool(c0 & 0x01)
                packet.metadata['freq_change'] = bool(c0 & 0x02)

        self.logger.debug(f"Data packet: seq={packet.sequence_number}")

        return packet

    def create_discovery_request(self) -> bytes:
        """
        Create a discovery request packet

        Returns:
            Discovery request packet bytes
        """
        packet = bytearray(63)
        packet[0:2] = self.DISCOVERY_SYNC
        packet[2] = self.CMD_DISCOVERY
        # Rest is zeros (padding)
        return bytes(packet)

    def create_discovery_response(
        self,
        mac_address: str,
        board_id: int = 0x06,  # Hermes Lite 2
        firmware_version: str = "1.0.0"
    ) -> bytes:
        """
        Create a discovery response packet (for testing)

        Args:
            mac_address: MAC address in format "aa:bb:cc:dd:ee:ff"
            board_id: Board ID
            firmware_version: Firmware version string

        Returns:
            Discovery response packet bytes
        """
        packet = bytearray(60)
        packet[0:2] = self.DISCOVERY_SYNC
        packet[2] = self.CMD_DISCOVERY

        # MAC address
        mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
        packet[3:9] = mac_bytes

        # Board ID
        packet[9] = board_id

        # Firmware version (simplified)
        fw_parts = firmware_version.split('.')
        for i, part in enumerate(fw_parts[:5]):
            packet[10 + i] = int(part)

        return bytes(packet)

    def is_start_command(self, packet: HPSDRPacket) -> bool:
        """
        Check if packet contains a start command

        Args:
            packet: Parsed packet

        Returns:
            True if this is a start command
        """
        if packet.packet_type != HPSDRPacketType.DATA:
            return False

        # Start command is indicated by specific control bytes
        # In Protocol 1, bit in C0 indicates start/stop
        if packet.command_bytes and len(packet.command_bytes) > 0:
            c0 = packet.command_bytes[0]
            # Bit 2 of C0 typically indicates start (implementation-specific)
            return bool(c0 & 0x04)

        return False

    def is_stop_command(self, packet: HPSDRPacket) -> bool:
        """
        Check if packet contains a stop command

        Args:
            packet: Parsed packet

        Returns:
            True if this is a stop command
        """
        # Similar to start command detection
        # This is a simplified implementation
        return False

    def extract_frequency(self, packet: HPSDRPacket) -> Optional[int]:
        """
        Extract frequency from data packet

        Args:
            packet: Parsed packet

        Returns:
            Frequency in Hz, or None if not available
        """
        if packet.packet_type != HPSDRPacketType.DATA:
            return None

        if not packet.command_bytes or len(packet.command_bytes) < 5:
            return None

        # Frequency is typically in bytes C1-C4 (4 bytes, big-endian)
        # Frequency in Hz = value × 122.88 MHz / 2^32
        freq_word = struct.unpack('>I', packet.command_bytes[1:5])[0]
        frequency_hz = int(freq_word * 122.88e6 / (2**32))

        return frequency_hz

    def get_statistics(self) -> Dict[str, int]:
        """
        Get packet processing statistics

        Returns:
            Statistics dictionary
        """
        return self.stats.copy()

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'total_packets': 0,
            'discovery_packets': 0,
            'data_packets': 0,
            'unknown_packets': 0,
            'error_packets': 0,
        }
