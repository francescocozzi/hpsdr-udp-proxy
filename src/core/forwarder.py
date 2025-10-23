"""
Packet Forwarder for HPSDR Proxy

Handles bidirectional packet forwarding between clients and radios.
"""
import asyncio
from typing import Optional, Tuple, Dict
from datetime import datetime

from .udp_listener import UDPListener
from .session_manager import SessionManager
from ..auth import DatabaseManager
from ..utils import get_logger, log_performance


class PacketForwarder:
    """
    Bidirectional packet forwarder

    Features:
    - Transparent packet forwarding
    - Session-based routing
    - Statistics collection
    - Low-latency operation
    """

    def __init__(
        self,
        client_listener: UDPListener,
        session_manager: SessionManager,
        db_manager: Optional[DatabaseManager] = None,
        collect_stats: bool = True,
        stats_interval: int = 60
    ):
        """
        Initialize packet forwarder

        Args:
            client_listener: UDP listener for client connections
            session_manager: Session manager instance
            db_manager: Optional database manager for statistics
            collect_stats: Whether to collect statistics
            stats_interval: Statistics collection interval in seconds
        """
        self.client_listener = client_listener
        self.session_manager = session_manager
        self.db = db_manager
        self.collect_stats = collect_stats
        self.stats_interval = stats_interval

        self.logger = get_logger(__name__)

        # Statistics
        self.stats = {
            'packets_forwarded_to_radio': 0,
            'packets_forwarded_to_client': 0,
            'bytes_forwarded_to_radio': 0,
            'bytes_forwarded_to_client': 0,
            'errors': 0,
            'dropped_no_session': 0,
            'dropped_no_radio': 0,
        }

        # Per-session statistics
        self.session_stats: Dict[int, Dict] = {}

        # Stats collection task
        self._stats_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the forwarder and statistics collection"""
        if self._running:
            self.logger.warning("Forwarder already running")
            return

        self.logger.info("Starting packet forwarder...")

        self._running = True

        # Start statistics collection task
        if self.collect_stats and self.db:
            self._stats_task = asyncio.create_task(self._stats_collection_loop())

        self.logger.info("Packet forwarder started")

    async def stop(self):
        """Stop the forwarder"""
        if not self._running:
            return

        self.logger.info("Stopping packet forwarder...")

        self._running = False

        if self._stats_task:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Packet forwarder stopped")

    # @log_performance(get_logger(__name__), threshold_ms=5.0)  # Temporarily disabled for debugging
    async def forward_to_radio(
        self,
        data: bytes,
        client_ip: str,
        client_port: int
    ) -> bool:
        """
        Forward packet from client to radio

        Args:
            data: Packet data
            client_ip: Client IP address
            client_port: Client port

        Returns:
            True if forwarded successfully, False otherwise
        """
        print(f"🔥🔥🔥 PRINT STATEMENT - ENTERED forward_to_radio for {client_ip}:{client_port}, {len(data)} bytes 🔥🔥🔥")
        try:
            print(f"💚 About to call logger.info")
            self.logger.info(f"⏩ [FORWARDER] Entered forward_to_radio for {client_ip}:{client_port}, {len(data)} bytes")
            print(f"💚 Logger.info called successfully")

            # Get session
            print(f"💙 Getting session for {client_ip}:{client_port}")
            session = self.session_manager.get_session_by_client(client_ip, client_port)
            print(f"💙 Session result: {session is not None}, radio_address: {session.radio_address if session else 'NO SESSION'}")
            self.logger.info(f"⏩ [FORWARDER] Session lookup result: {session is not None}")

            if not session:
                print(f"❌ NO SESSION - returning False")
                self.logger.warning(f"❌ No session for client {client_ip}:{client_port} - dropping packet")
                self.stats['dropped_no_session'] += 1
                return False

            # Get radio address
            radio_address = session.radio_address

            if not radio_address:
                print(f"❌ NO RADIO ADDRESS - returning False")
                self.logger.warning(f"❌ No radio assigned for client {client_ip}:{client_port} - dropping packet")
                self.stats['dropped_no_radio'] += 1
                return False

            # Forward packet
            print(f"💜 About to send {len(data)} bytes to {radio_address[0]}:{radio_address[1]}")
            self.logger.info(f"📤 [FORWARDER] About to send {len(data)} bytes to {radio_address[0]}:{radio_address[1]}")
            await self.client_listener.send_to(data, radio_address)
            print(f"💜 Packet sent successfully!")
            self.logger.info(f"📤 [FORWARDER] Packet sent successfully to radio")

            # Update statistics
            self.stats['packets_forwarded_to_radio'] += 1
            self.stats['bytes_forwarded_to_radio'] += len(data)

            # Update session activity
            await self.session_manager.update_activity(client_ip, client_port)

            # Update per-session statistics
            if session.session_id not in self.session_stats:
                self.session_stats[session.session_id] = {
                    'packets_sent': 0,
                    'packets_received': 0,
                    'bytes_sent': 0,
                    'bytes_received': 0,
                    'start_time': datetime.utcnow(),
                }

            self.session_stats[session.session_id]['packets_sent'] += 1
            self.session_stats[session.session_id]['bytes_sent'] += len(data)

            self.logger.info(
                f"→ Forwarded {len(data)} bytes from {client_ip}:{client_port} "
                f"to radio {radio_address[0]}:{radio_address[1]}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error forwarding packet to radio: {e}")
            self.stats['errors'] += 1
            return False

    @log_performance(get_logger(__name__), threshold_ms=5.0)
    async def forward_to_client(
        self,
        data: bytes,
        radio_ip: str,
        radio_port: int
    ) -> bool:
        """
        Forward packet from radio to client

        Args:
            data: Packet data
            radio_ip: Radio IP address
            radio_port: Radio port

        Returns:
            True if forwarded successfully, False otherwise
        """
        try:
            # Find client for this radio
            client_address = self.session_manager.get_client_for_radio(radio_ip, radio_port)

            if not client_address:
                self.logger.warning(f"❌ No client for radio {radio_ip}:{radio_port} - dropping response")
                # This is normal - radio might be sending broadcasts
                return False

            # Get session to update stats
            session = self.session_manager.get_session_by_client(
                client_address[0],
                client_address[1]
            )

            # Forward packet
            await self.client_listener.send_to(data, client_address)

            # Update statistics
            self.stats['packets_forwarded_to_client'] += 1
            self.stats['bytes_forwarded_to_client'] += len(data)

            # Update per-session statistics
            if session and session.session_id in self.session_stats:
                self.session_stats[session.session_id]['packets_received'] += 1
                self.session_stats[session.session_id]['bytes_received'] += len(data)

            self.logger.info(
                f"← Forwarded {len(data)} bytes from radio {radio_ip}:{radio_port} "
                f"to client {client_address[0]}:{client_address[1]}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error forwarding packet to client: {e}")
            self.stats['errors'] += 1
            return False

    async def _stats_collection_loop(self):
        """Background task to periodically save statistics to database"""
        self.logger.info("Statistics collection task started")

        while self._running:
            try:
                await asyncio.sleep(self.stats_interval)
                await self._save_statistics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in statistics collection: {e}")

        self.logger.info("Statistics collection task stopped")

    async def _save_statistics(self):
        """Save statistics to database"""
        if not self.db:
            return

        try:
            # Save per-session statistics
            for session_id, stats in list(self.session_stats.items()):
                # Get session info
                session = self.session_manager.sessions_by_id.get(session_id)

                if not session:
                    # Session no longer exists, remove stats
                    del self.session_stats[session_id]
                    continue

                # Record statistics
                await self.db.record_statistics(
                    radio_id=session.radio_id,
                    session_id=session_id,
                    packets_received=stats['packets_received'],
                    packets_sent=stats['packets_sent'],
                    bytes_received=stats['bytes_received'],
                    bytes_sent=stats['bytes_sent'],
                    interval_seconds=self.stats_interval
                )

                # Reset counters
                stats['packets_sent'] = 0
                stats['packets_received'] = 0
                stats['bytes_sent'] = 0
                stats['bytes_received'] = 0

            self.logger.debug("Statistics saved to database")

        except Exception as e:
            self.logger.error(f"Error saving statistics: {e}")

    def get_statistics(self) -> Dict:
        """
        Get forwarder statistics

        Returns:
            Dictionary with statistics
        """
        return {
            **self.stats,
            'active_sessions': len(self.session_stats),
        }

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'packets_forwarded_to_radio': 0,
            'packets_forwarded_to_client': 0,
            'bytes_forwarded_to_radio': 0,
            'bytes_forwarded_to_client': 0,
            'errors': 0,
            'dropped_no_session': 0,
            'dropped_no_radio': 0,
        }
        self.logger.info("Statistics reset")

    def get_throughput(self) -> Tuple[float, float]:
        """
        Get throughput in packets/second

        Returns:
            Tuple of (to_radio_pps, to_client_pps)
        """
        # Calculate approximate throughput
        # This is a simple estimate based on stats interval
        if self.stats_interval > 0:
            to_radio_pps = self.stats['packets_forwarded_to_radio'] / self.stats_interval
            to_client_pps = self.stats['packets_forwarded_to_client'] / self.stats_interval
            return (to_radio_pps, to_client_pps)

        return (0.0, 0.0)

    def get_bandwidth(self) -> Tuple[float, float]:
        """
        Get bandwidth in Mbps

        Returns:
            Tuple of (to_radio_mbps, to_client_mbps)
        """
        # Calculate approximate bandwidth
        if self.stats_interval > 0:
            to_radio_mbps = (self.stats['bytes_forwarded_to_radio'] * 8) / (self.stats_interval * 1_000_000)
            to_client_mbps = (self.stats['bytes_forwarded_to_client'] * 8) / (self.stats_interval * 1_000_000)
            return (to_radio_mbps, to_client_mbps)

        return (0.0, 0.0)
