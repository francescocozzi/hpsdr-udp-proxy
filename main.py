#!/usr/bin/env python3
"""
HPSDR UDP Proxy/Gateway - Main Entry Point

A high-performance UDP proxy for HPSDR protocol with authentication.
"""
import asyncio
import signal
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, setup_logger, get_logger
from src.core import UDPListener, PacketHandler
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

        self.logger.info("=" * 60)
        self.logger.info("HPSDR UDP Proxy/Gateway Starting...")
        self.logger.info("=" * 60)

        # Initialize components
        self.udp_listener: UDPListener = None
        self.packet_handler: PacketHandler = None
        self.db_manager: DatabaseManager = None
        self.auth_manager: AuthManager = None

        self._running = False

    async def initialize(self):
        """Initialize all components"""
        self.logger.info("Initializing components...")

        # Initialize packet handler
        self.packet_handler = PacketHandler()
        self.logger.info("✓ Packet handler initialized")

        # Initialize database
        self.logger.info("Connecting to database...")
        # TODO: Initialize database manager
        # self.db_manager = DatabaseManager(self.config.database)
        # await self.db_manager.connect()
        # self.logger.info("✓ Database connected")

        # Initialize authentication manager
        # TODO: Initialize auth manager
        # self.auth_manager = AuthManager(self.db_manager, self.config.auth)
        # self.logger.info("✓ Authentication manager initialized")

        # Initialize UDP listener
        self.udp_listener = UDPListener(
            listen_address=self.config.proxy.listen_address,
            listen_port=self.config.proxy.listen_port,
            buffer_size=self.config.proxy.buffer_size
        )
        self.udp_listener.set_packet_callback(self._handle_packet)
        await self.udp_listener.start()
        self.logger.info("✓ UDP listener started")

        self.logger.info("All components initialized successfully!")

    async def _handle_packet(self, data: bytes, addr: tuple):
        """
        Handle incoming UDP packet

        Args:
            data: Packet data
            addr: Sender address (ip, port)
        """
        # Parse packet
        packet = self.packet_handler.parse(data)

        self.logger.debug(f"Received packet from {addr[0]}:{addr[1]} - {packet}")

        # TODO: Implement authentication and forwarding logic
        # For now, just log the packet
        if packet.packet_type.name == "DISCOVERY":
            self.logger.info(f"Discovery packet from {addr[0]}:{addr[1]}")
            # TODO: Check authentication and forward to radio

        elif packet.packet_type.name == "DATA":
            # TODO: Check session and forward
            pass

    async def run(self):
        """Main run loop"""
        await self.initialize()

        self._running = True
        self.logger.info("Proxy is now running. Press Ctrl+C to stop.")

        try:
            # Keep running until interrupted
            while self._running:
                await asyncio.sleep(1)

                # Periodic tasks can go here
                # - Session cleanup
                # - Statistics collection
                # - Health checks

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")

        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down proxy...")

        self._running = False

        # Stop UDP listener
        if self.udp_listener:
            await self.udp_listener.stop()
            self.logger.info("✓ UDP listener stopped")

        # Close database connection
        if self.db_manager:
            # await self.db_manager.disconnect()
            self.logger.info("✓ Database disconnected")

        # Print statistics
        if self.packet_handler:
            stats = self.packet_handler.get_statistics()
            self.logger.info(f"Packet statistics: {stats}")

        if self.udp_listener:
            stats = self.udp_listener.get_statistics()
            self.logger.info(f"UDP statistics: {stats}")

        self.logger.info("Shutdown complete.")


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
        description='HPSDR UDP Proxy/Gateway with Authentication'
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
        version='HPSDR Proxy 0.1.0'
    )

    args = parser.parse_args()

    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {args.config}")
        print(f"Please create it from the example:")
        print(f"  cp config/config.yaml.example {args.config}")
        sys.exit(1)

    # Create proxy instance
    try:
        proxy_instance = HPSDRProxy(args.config)

        # Override log level if verbose
        if args.verbose:
            proxy_instance.config.logging.level = "DEBUG"

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run proxy
        await proxy_instance.run()

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
