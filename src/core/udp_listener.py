"""
UDP Listener for HPSDR Proxy

Handles incoming UDP packets from HPSDR clients and radios using asyncio.
"""
import asyncio
import socket
from typing import Callable, Optional, Tuple, Dict
from dataclasses import dataclass
from ..utils import get_logger, log_performance, log_exceptions


@dataclass
class UDPEndpoint:
    """Represents a UDP endpoint (address and port)"""
    address: str
    port: int

    def __str__(self):
        return f"{self.address}:{self.port}"

    def as_tuple(self) -> Tuple[str, int]:
        return (self.address, self.port)


class UDPProtocol(asyncio.DatagramProtocol):
    """
    AsyncIO DatagramProtocol for handling UDP packets
    """

    def __init__(self, packet_callback: Callable):
        """
        Initialize UDP protocol

        Args:
            packet_callback: Callback function called when packet is received
                            Signature: async def callback(data: bytes, addr: Tuple[str, int])
        """
        self.packet_callback = packet_callback
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.logger = get_logger(__name__)

    def connection_made(self, transport: asyncio.DatagramTransport):
        """Called when connection is established"""
        self.transport = transport
        sock = transport.get_extra_info('socket')
        sock_name = sock.getsockname()
        self.logger.info(f"UDP listener started on {sock_name[0]}:{sock_name[1]}")

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        """
        Called when a datagram is received

        Args:
            data: Received data bytes
            addr: Sender address (ip, port)
        """
        # Schedule packet processing without blocking
        asyncio.create_task(self._process_packet(data, addr))

    async def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        """
        Process received packet asynchronously

        Args:
            data: Packet data
            addr: Sender address
        """
        try:
            await self.packet_callback(data, addr)
        except Exception as e:
            self.logger.exception(f"Error processing packet from {addr}: {e}")

    def error_received(self, exc: Exception):
        """Called when an error is received"""
        self.logger.error(f"UDP error: {exc}")

    def connection_lost(self, exc: Optional[Exception]):
        """Called when connection is lost"""
        if exc:
            self.logger.error(f"UDP connection lost: {exc}")
        else:
            self.logger.info("UDP listener stopped")


class UDPListener:
    """
    High-performance UDP listener for HPSDR proxy

    Listens on a specified address/port and forwards received packets
    to a callback function for processing.
    """

    def __init__(
        self,
        listen_address: str = "0.0.0.0",
        listen_port: int = 1024,
        buffer_size: int = 2048
    ):
        """
        Initialize UDP listener

        Args:
            listen_address: Address to bind to
            listen_port: Port to bind to
            buffer_size: Maximum packet size to receive
        """
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.buffer_size = buffer_size

        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[UDPProtocol] = None
        self.logger = get_logger(__name__)

        self._running = False
        self._packet_callback: Optional[Callable] = None

        # Statistics
        self.stats = {
            'packets_received': 0,
            'bytes_received': 0,
            'errors': 0,
        }

    def set_packet_callback(self, callback: Callable):
        """
        Set callback function for received packets

        Args:
            callback: Async function with signature: async def callback(data: bytes, addr: Tuple[str, int])
        """
        self._packet_callback = callback

    async def start(self):
        """
        Start the UDP listener

        Raises:
            RuntimeError: If no packet callback is set
        """
        if self._packet_callback is None:
            raise RuntimeError("Packet callback not set. Call set_packet_callback() first.")

        if self._running:
            self.logger.warning("UDP listener already running")
            return

        self.logger.info(f"Starting UDP listener on {self.listen_address}:{self.listen_port}")

        try:
            # Get the event loop
            loop = asyncio.get_running_loop()

            # Create UDP endpoint
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self._handle_packet),
                local_addr=(self.listen_address, self.listen_port),
                reuse_port=True,  # Allow multiple processes to bind
            )

            # Set socket options for better performance
            sock = self.transport.get_extra_info('socket')
            if sock:
                # Increase receive buffer size
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size * 100)

                # Enable broadcast (for discovery packets)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                # Set socket to non-blocking mode (should already be set by asyncio)
                sock.setblocking(False)

            self._running = True
            self.logger.info("UDP listener started successfully")

        except Exception as e:
            self.logger.exception(f"Failed to start UDP listener: {e}")
            raise

    @log_performance(get_logger(__name__), threshold_ms=5.0)
    async def _handle_packet(self, data: bytes, addr: Tuple[str, int]):
        """
        Internal packet handler with statistics tracking

        Args:
            data: Packet data
            addr: Sender address
        """
        try:
            # Update statistics
            self.stats['packets_received'] += 1
            self.stats['bytes_received'] += len(data)

            # Log packet details (debug level)
            self.logger.debug(
                f"Received {len(data)} bytes from {addr[0]}:{addr[1]}"
            )

            # Call user callback
            if self._packet_callback:
                await self._packet_callback(data, addr)

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.exception(f"Error handling packet: {e}")

    async def send_to(self, data: bytes, addr: Tuple[str, int]):
        """
        Send data to a specific address

        Args:
            data: Data to send
            addr: Destination address (ip, port)
        """
        if not self._running or not self.transport:
            raise RuntimeError("UDP listener not running")

        try:
            self.transport.sendto(data, addr)
            self.logger.debug(f"Sent {len(data)} bytes to {addr[0]}:{addr[1]}")
        except Exception as e:
            self.logger.error(f"Error sending data to {addr}: {e}")
            raise

    async def stop(self):
        """Stop the UDP listener"""
        if not self._running:
            self.logger.warning("UDP listener not running")
            return

        self.logger.info("Stopping UDP listener...")

        if self.transport:
            self.transport.close()
            self.transport = None

        self.protocol = None
        self._running = False

        self.logger.info("UDP listener stopped")

    def is_running(self) -> bool:
        """Check if listener is running"""
        return self._running

    def get_statistics(self) -> Dict:
        """
        Get listener statistics

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'packets_received': 0,
            'bytes_received': 0,
            'errors': 0,
        }
        self.logger.debug("Statistics reset")

    def get_local_address(self) -> Optional[Tuple[str, int]]:
        """
        Get the local address the listener is bound to

        Returns:
            Tuple of (address, port) or None if not running
        """
        if not self.transport:
            return None

        sock = self.transport.get_extra_info('socket')
        if sock:
            return sock.getsockname()

        return None


class MultiPortUDPListener:
    """
    UDP listener that can listen on multiple ports simultaneously

    Useful for handling both client connections and radio responses
    on different ports.
    """

    def __init__(self):
        """Initialize multi-port listener"""
        self.listeners: Dict[int, UDPListener] = {}
        self.logger = get_logger(__name__)

    async def add_listener(
        self,
        port: int,
        callback: Callable,
        address: str = "0.0.0.0",
        buffer_size: int = 2048
    ):
        """
        Add a listener on a specific port

        Args:
            port: Port to listen on
            callback: Packet callback function
            address: Address to bind to
            buffer_size: Buffer size for packets
        """
        if port in self.listeners:
            raise ValueError(f"Listener already exists on port {port}")

        listener = UDPListener(address, port, buffer_size)
        listener.set_packet_callback(callback)
        await listener.start()

        self.listeners[port] = listener
        self.logger.info(f"Added listener on port {port}")

    async def remove_listener(self, port: int):
        """
        Remove and stop a listener

        Args:
            port: Port of listener to remove
        """
        if port not in self.listeners:
            raise ValueError(f"No listener on port {port}")

        listener = self.listeners[port]
        await listener.stop()
        del self.listeners[port]

        self.logger.info(f"Removed listener on port {port}")

    async def stop_all(self):
        """Stop all listeners"""
        self.logger.info("Stopping all listeners...")

        for port, listener in list(self.listeners.items()):
            await listener.stop()

        self.listeners.clear()
        self.logger.info("All listeners stopped")

    def get_listener(self, port: int) -> Optional[UDPListener]:
        """
        Get listener by port

        Args:
            port: Port number

        Returns:
            UDPListener instance or None
        """
        return self.listeners.get(port)

    def get_all_statistics(self) -> Dict[int, Dict]:
        """
        Get statistics for all listeners

        Returns:
            Dictionary mapping port to statistics
        """
        return {
            port: listener.get_statistics()
            for port, listener in self.listeners.items()
        }
