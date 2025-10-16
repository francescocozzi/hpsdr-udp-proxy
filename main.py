#!/usr/bin/env python3
"""
HPSDR UDP Proxy/Gateway - Main Entry Point

A high-performance UDP proxy for HPSDR protocol with authentication.
Version: 0.2.0-alpha
"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional, Tuple

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, setup_logger, get_logger
from src.core import UDPListener, PacketHandler, SessionManager, PacketForwarder, HPSDRPacketType
from src.auth import DatabaseManager, AuthManager

# Global references for graceful shutdown
proxy_instance = None


class HPSDRProxy:
    """
    Main HPSDR Proxy application

    Coordinates all components: UDP listener, packet handler,
    authentication, session management, and packet forwarding.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize HPSDR Proxy

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = load_config(config_path)

        # Setup logging
        self.logger = setup_logger(
            'hpsdr_proxy',
            self.config.logging
        )

        self.logger.info("=" * 70)
        self.logger.info("HPSDR UDP Proxy/Gateway v0.2.0-alpha Starting...")
        self.logger.info("=" * 70)

        # Components
        self.udp_listener: Optional[UDPListener] = None
        self.packet_handler: Optional[PacketHandler] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.auth_manager: Optional[AuthManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.packet_forwarder: Optional[PacketForwarder] = None

        # State
        self._running = False
        self._allow_anonymous = not self.config.security.require_authentication

        # Radio mapping (from config)
        self.radios = {radio.ip: radio for radio in self.config.get_enabled_radios()}

        # Mapping from resolved IP to radio (for packet routing)
        self.radio_ips = {}  # Will be populated in initialize()

    async def _resolve_radio_ips(self):
        """Resolve radio hostnames to IP addresses for packet routing"""
        import socket

        self.radio_ips = {}

        for hostname, radio in self.radios.items():
            try:
                # Resolve hostname to IP
                resolved_ip = socket.gethostbyname(hostname)
                self.radio_ips[resolved_ip] = radio
                self.logger.info(f"Resolved {hostname} → {resolved_ip}")

            except socket.gaierror as e:
                self.logger.error(f"Failed to resolve {hostname}: {e}")
                # Keep hostname in mapping as fallback
                self.radio_ips[hostname] = radio

    async def initialize(self):
        """Initialize all components"""
        self.logger.info("Initializing components...")

        # Resolve radio hostnames to IPs for packet routing
        await self._resolve_radio_ips()

        # 1. Initialize packet handler
        self.packet_handler = PacketHandler()
        self.logger.info("✓ Packet handler initialized")

        # 2. Initialize database
        self.logger.info("Connecting to database...")
        connection_string = self.config.database.get_connection_string()
        self.db_manager = DatabaseManager(
            connection_string=connection_string,
            pool_size=self.config.database.pool_size,
            max_overflow=self.config.database.max_overflow
        )
        await self.db_manager.connect()

        # Check database health
        if not await self.db_manager.health_check():
            raise RuntimeError("Database health check failed")

        self.logger.info("✓ Database connected")

        # 3. Initialize authentication manager
        self.auth_manager = AuthManager(
            db_manager=self.db_manager,
            jwt_secret=self.config.auth.jwt_secret,
            jwt_algorithm=self.config.auth.jwt_algorithm,
            token_expiry=self.config.auth.token_expiry,
            refresh_token_expiry=self.config.auth.refresh_token_expiry,
            max_login_attempts=self.config.auth.max_login_attempts,
            lockout_duration=self.config.auth.lockout_duration
        )
        self.logger.info("✓ Authentication manager initialized")

        # 4. Initialize session manager
        self.session_manager = SessionManager(
            db_manager=self.db_manager,
            auth_manager=self.auth_manager,
            session_timeout=self.config.proxy.session_timeout,
            cleanup_interval=30
        )
        await self.session_manager.start()
        self.logger.info("✓ Session manager started")

        # 5. Initialize UDP listener
        self.udp_listener = UDPListener(
            listen_address=self.config.proxy.listen_address,
            listen_port=self.config.proxy.listen_port,
            buffer_size=self.config.proxy.buffer_size
        )
        self.udp_listener.set_packet_callback(self._handle_client_packet)
        await self.udp_listener.start()
        self.logger.info(f"✓ UDP listener started on {self.config.proxy.listen_address}:{self.config.proxy.listen_port}")

        # 6. Initialize packet forwarder
        self.packet_forwarder = PacketForwarder(
            client_listener=self.udp_listener,
            session_manager=self.session_manager,
            db_manager=self.db_manager,
            collect_stats=self.config.performance.stats_enabled,
            stats_interval=self.config.performance.stats_interval
        )
        await self.packet_forwarder.start()
        self.logger.info("✓ Packet forwarder started")

        # Log configuration summary
        self.logger.info(f"Configuration: {len(self.radios)} radio(s), "
                        f"auth={'required' if not self._allow_anonymous else 'optional'}")

        for radio in self.radios.values():
            self.logger.info(f"  - Radio: {radio.name} ({radio.ip}:{radio.port})")

        self.logger.info("=" * 70)
        self.logger.info("All components initialized successfully!")
        self.logger.info("=" * 70)

    async def _handle_client_packet(self, data: bytes, addr: Tuple[str, int]):
        """
        Handle incoming packet from client

        Args:
            data: Packet data
            addr: Client address (ip, port)
        """
        client_ip, client_port = addr

        try:
            # Check if packet is from a configured radio (response, not request)
            # Use resolved IPs for matching (radio_ips contains IP→radio mapping)
            is_from_radio = client_ip in self.radio_ips

            if is_from_radio:
                # This is a response FROM the radio TO a client
                # Forward it to the appropriate client
                self.logger.info(f"✓ Received response from radio {client_ip}:{client_port} - forwarding to client")
                await self.packet_forwarder.forward_to_client(data, client_ip, client_port)
                return

            # Parse packet from client
            packet = self.packet_handler.parse(data)

            # Handle discovery packets
            if packet.packet_type == HPSDRPacketType.DISCOVERY:
                await self._handle_discovery(packet, client_ip, client_port, data)

            # Handle data packets
            elif packet.packet_type == HPSDRPacketType.DATA:
                await self._handle_data(packet, client_ip, client_port, data)

            # Handle other packet types (including UNKNOWN - likely data packets)
            else:
                # Treat UNKNOWN packets as data packets (common for HPSDR Protocol 1)
                if packet.packet_type == HPSDRPacketType.UNKNOWN:
                    self.logger.debug(f"UNKNOWN packet from {client_ip}:{client_port} - treating as DATA")
                    await self._handle_data(packet, client_ip, client_port, data)
                else:
                    self.logger.info(f"⚠️ Unhandled {packet.packet_type.name} packet from {client_ip}:{client_port} - forwarding anyway")
                    # Forward packet (best effort)
                    await self.packet_forwarder.forward_to_radio(data, client_ip, client_port)

        except Exception as e:
            self.logger.error(f"Error handling packet from {client_ip}:{client_port}: {e}")

    async def _handle_discovery(self, packet, client_ip: str, client_port: int, data: bytes):
        """Handle discovery packet from client"""
        self.logger.info(f"Discovery from {client_ip}:{client_port}")

        # Check/validate session
        is_valid, session = await self.session_manager.validate_client(
            client_ip,
            client_port,
            token=None  # TODO: Extract token from packet if present
        )

        if not is_valid and not self._allow_anonymous:
            self.logger.warning(f"Discovery from unauthenticated client {client_ip}:{client_port}")
            # TODO: Send authentication required response
            return

        # Get first available radio (simple strategy)
        if not self.radios:
            self.logger.error("No radios configured")
            return

        radio = list(self.radios.values())[0]

        # Get resolved IP for this radio
        resolved_radio_ip = None
        for ip, r in self.radio_ips.items():
            if r == radio:
                resolved_radio_ip = ip
                break

        if not resolved_radio_ip:
            self.logger.error(f"No resolved IP found for radio {radio.name}")
            return

        # Create or get session for anonymous client (needed for forwarding)
        if not session and self._allow_anonymous:
            session = self.session_manager.create_anonymous_session(
                client_ip,
                client_port
            )
            self.logger.debug(f"Created anonymous session for {client_ip}:{client_port}")

        # Assign radio to session using RESOLVED IP
        if session:
            self.session_manager.assign_radio(
                client_ip,
                client_port,
                resolved_radio_ip,  # Use resolved IP instead of hostname
                radio.port,
                radio_id=None  # TODO: Get radio ID from database
            )
            self.logger.info(f"Assigned radio {radio.name} ({resolved_radio_ip}:{radio.port}) to client {client_ip}:{client_port}")

        # Forward discovery to radio
        self.logger.info(f"Forwarding discovery to radio {radio.ip}:{radio.port}")
        await self.packet_forwarder.forward_to_radio(data, client_ip, client_port)

        # Start listening for radio response in background
        asyncio.create_task(self._listen_for_radio_response(radio.ip, radio.port, client_ip, client_port))

    async def _handle_data(self, packet, client_ip: str, client_port: int, data: bytes):
        """Handle data packet from client"""

        # Check session
        session = self.session_manager.get_session_by_client(client_ip, client_port)

        if not session:
            if self._allow_anonymous:
                # Create session on-the-fly for data packets too
                self.logger.debug(f"Creating anonymous session for data from {client_ip}:{client_port}")
                session = self.session_manager.create_anonymous_session(client_ip, client_port)

                # Assign same radio as discovery
                radio = list(self.radios.values())[0]
                resolved_radio_ip = None
                for ip, r in self.radio_ips.items():
                    if r == radio:
                        resolved_radio_ip = ip
                        break

                if resolved_radio_ip:
                    self.session_manager.assign_radio(
                        client_ip,
                        client_port,
                        resolved_radio_ip,
                        radio.port,
                        radio_id=None
                    )
            else:
                self.logger.warning(f"Data packet from {client_ip}:{client_port} - no session, dropping")
                return

        # Forward to radio
        await self.packet_forwarder.forward_to_radio(data, client_ip, client_port)

    async def _listen_for_radio_response(self, radio_ip: str, radio_port: int, client_ip: str, client_port: int):
        """
        Listen for responses from radio and forward to client

        This is a simplified implementation. In production, you'd want a
        more sophisticated approach with a separate listener for radio responses.
        """
        # For now, the forwarder will handle this when we receive packets
        # from the radio on the same socket
        pass

    async def run(self):
        """Main run loop"""
        try:
            await self.initialize()

            self._running = True
            self.logger.info("🚀 Proxy is now running. Press Ctrl+C to stop.")
            self.logger.info("")

            # Main loop
            while self._running:
                await asyncio.sleep(5)

                # Periodic status report
                if self.session_manager:
                    active_sessions = self.session_manager.get_session_count()
                    if active_sessions > 0:
                        self.logger.debug(f"Active sessions: {active_sessions}")

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")

        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("Shutting down proxy...")
        self.logger.info("=" * 70)

        self._running = False

        # Stop packet forwarder
        if self.packet_forwarder:
            await self.packet_forwarder.stop()
            self.logger.info("✓ Packet forwarder stopped")

        # Stop session manager
        if self.session_manager:
            await self.session_manager.stop()
            self.logger.info("✓ Session manager stopped")

        # Stop UDP listener
        if self.udp_listener:
            await self.udp_listener.stop()
            self.logger.info("✓ UDP listener stopped")

        # Close database connection
        if self.db_manager:
            await self.db_manager.disconnect()
            self.logger.info("✓ Database disconnected")

        # Print final statistics
        self.logger.info("")
        self.logger.info("Final Statistics:")
        self.logger.info("-" * 70)

        if self.packet_handler:
            stats = self.packet_handler.get_statistics()
            self.logger.info(f"  Packets processed: {stats['total_packets']}")
            self.logger.info(f"    - Discovery: {stats['discovery_packets']}")
            self.logger.info(f"    - Data: {stats['data_packets']}")
            self.logger.info(f"    - Unknown: {stats['unknown_packets']}")
            self.logger.info(f"    - Errors: {stats['error_packets']}")

        if self.udp_listener:
            stats = self.udp_listener.get_statistics()
            self.logger.info(f"  UDP: {stats['packets_received']} received, {stats['bytes_received']} bytes")

        if self.packet_forwarder:
            stats = self.packet_forwarder.get_statistics()
            self.logger.info(f"  Forwarded: {stats['packets_forwarded_to_radio']} to radio, "
                           f"{stats['packets_forwarded_to_client']} to client")

        if self.session_manager:
            stats = self.session_manager.get_statistics()
            self.logger.info(f"  Sessions: {stats['total_sessions']} total, "
                           f"{stats['expired_sessions']} expired, {stats['timeouts']} timeouts")

        self.logger.info("=" * 70)
        self.logger.info("Shutdown complete. Goodbye!")
        self.logger.info("=" * 70)


def signal_handler(sig, frame):
    """Handle termination signals"""
    logger = get_logger('hpsdr_proxy')
    logger.info(f"Received signal {sig}")

    if proxy_instance and proxy_instance._running:
        proxy_instance._running = False


async def main():
    """Main entry point"""
    global proxy_instance

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='HPSDR UDP Proxy/Gateway with Authentication',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run with default config
  %(prog)s -c custom.yaml            # Run with custom config
  %(prog)s -v                        # Run with verbose logging
  %(prog)s --version                 # Show version

For more information, see: https://github.com/francescocozzi/hpsdr-udp-proxy
        """
    )
    parser.add_argument(
        '-c', '--config',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='HPSDR Proxy 0.2.0-alpha'
    )

    args = parser.parse_args()

    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Error: Configuration file not found: {args.config}")
        print(f"")
        print(f"Please create it from the example:")
        print(f"  cp config/config.yaml.example {args.config}")
        print(f"")
        print(f"Then edit it with your settings:")
        print(f"  nano {args.config}")
        print(f"")
        sys.exit(1)

    # Create proxy instance
    try:
        proxy_instance = HPSDRProxy(args.config)

        # Override log level if verbose
        if args.verbose:
            proxy_instance.config.logging.level = "DEBUG"
            proxy_instance.logger.setLevel("DEBUG")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run proxy
        await proxy_instance.run()

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(0)
