"""
Session Manager for HPSDR Proxy

Tracks active client sessions and manages client-to-radio mappings.
"""
import asyncio
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..auth import DatabaseManager, AuthManager, User
from ..utils import get_logger, log_exceptions


@dataclass
class ActiveSession:
    """
    In-memory session data for fast lookups

    This is kept in memory for performance, with periodic
    sync to database for persistence.
    """
    session_id: int
    user_id: int
    username: str
    token: str
    client_address: Tuple[str, int]  # (IP, port)
    radio_address: Optional[Tuple[str, int]]  # (IP, port)
    radio_id: Optional[int]
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    authenticated: bool = True

    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.utcnow() > self.expires_at

    def is_idle(self, timeout_seconds: int = 60) -> bool:
        """Check if session has been idle"""
        return (datetime.utcnow() - self.last_activity).total_seconds() > timeout_seconds

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()


class SessionManager:
    """
    Manages active client sessions and client-to-radio mappings

    Features:
    - Fast in-memory session lookups
    - Client address to radio mapping
    - Session timeout handling
    - Periodic cleanup of expired sessions
    - Statistics collection
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        auth_manager: AuthManager,
        session_timeout: int = 60,
        cleanup_interval: int = 30
    ):
        """
        Initialize session manager

        Args:
            db_manager: Database manager instance
            auth_manager: Authentication manager instance
            session_timeout: Session idle timeout in seconds
            cleanup_interval: Cleanup task interval in seconds
        """
        self.db = db_manager
        self.auth = auth_manager
        self.session_timeout = session_timeout
        self.cleanup_interval = cleanup_interval

        self.logger = get_logger(__name__)

        # In-memory session storage for fast lookups
        # Key: (client_ip, client_port)
        self.sessions_by_client: Dict[Tuple[str, int], ActiveSession] = {}

        # Key: token
        self.sessions_by_token: Dict[str, ActiveSession] = {}

        # Key: session_id
        self.sessions_by_id: Dict[int, ActiveSession] = {}

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self.stats = {
            'total_sessions': 0,
            'active_sessions': 0,
            'expired_sessions': 0,
            'timeouts': 0,
        }

    async def start(self):
        """Start session manager and cleanup task"""
        if self._running:
            self.logger.warning("Session manager already running")
            return

        self.logger.info("Starting session manager...")

        # Load active sessions from database
        await self._load_active_sessions()

        # Start cleanup task
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self.logger.info("Session manager started")

    async def stop(self):
        """Stop session manager"""
        if not self._running:
            return

        self.logger.info("Stopping session manager...")

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Session manager stopped")

    async def _load_active_sessions(self):
        """Load active sessions from database on startup"""
        try:
            sessions = await self.db.list_active_sessions()

            for db_session in sessions:
                active_session = ActiveSession(
                    session_id=db_session.id,
                    user_id=db_session.user_id,
                    username=db_session.user.username,
                    token=db_session.token,
                    client_address=(db_session.client_ip, db_session.client_port or 0),
                    radio_address=None,  # Will be set on first packet
                    radio_id=db_session.radio_id,
                    created_at=db_session.created_at,
                    expires_at=db_session.expires_at,
                    last_activity=db_session.last_activity or db_session.created_at,
                    authenticated=True
                )

                # Add to lookup tables
                self._add_session(active_session)

            self.logger.info(f"Loaded {len(sessions)} active sessions from database")

        except Exception as e:
            self.logger.error(f"Error loading sessions from database: {e}")

    def _add_session(self, session: ActiveSession):
        """Add session to all lookup tables"""
        self.sessions_by_client[session.client_address] = session
        self.sessions_by_token[session.token] = session
        self.sessions_by_id[session.session_id] = session

        self.stats['active_sessions'] = len(self.sessions_by_client)
        self.stats['total_sessions'] += 1

    def _remove_session(self, session: ActiveSession):
        """Remove session from all lookup tables"""
        self.sessions_by_client.pop(session.client_address, None)
        self.sessions_by_token.pop(session.token, None)
        self.sessions_by_id.pop(session.session_id, None)

        self.stats['active_sessions'] = len(self.sessions_by_client)

    @log_exceptions(get_logger(__name__))
    async def create_session(
        self,
        user: User,
        token: str,
        client_ip: str,
        client_port: int,
        expires_at: datetime,
        radio_id: Optional[int] = None
    ) -> ActiveSession:
        """
        Create a new session

        Args:
            user: User object
            token: Authentication token
            client_ip: Client IP address
            client_port: Client port
            expires_at: Expiration time
            radio_id: Optional radio ID

        Returns:
            ActiveSession object
        """
        client_address = (client_ip, client_port)

        # Check if session already exists
        existing = self.sessions_by_client.get(client_address)
        if existing:
            self.logger.warning(
                f"Session already exists for {client_ip}:{client_port}, replacing"
            )
            self._remove_session(existing)

        # Create session in database
        db_session = await self.db.create_session(
            user_id=user.id,
            token=token,
            client_ip=client_ip,
            client_port=client_port,
            expires_at=expires_at,
            radio_id=radio_id
        )

        # Create in-memory session
        session = ActiveSession(
            session_id=db_session.id,
            user_id=user.id,
            username=user.username,
            token=token,
            client_address=client_address,
            radio_address=None,
            radio_id=radio_id,
            created_at=db_session.created_at,
            expires_at=expires_at,
            last_activity=datetime.utcnow(),
            authenticated=True
        )

        # Add to lookup tables
        self._add_session(session)

        self.logger.info(f"Session created for user {user.username} from {client_ip}:{client_port}")

        return session

    def get_session_by_client(
        self,
        client_ip: str,
        client_port: int
    ) -> Optional[ActiveSession]:
        """
        Get session by client address

        Args:
            client_ip: Client IP
            client_port: Client port

        Returns:
            ActiveSession if found and valid, None otherwise
        """
        client_address = (client_ip, client_port)
        session = self.sessions_by_client.get(client_address)

        if not session:
            return None

        # Check if expired
        if session.is_expired():
            self.logger.debug(f"Session expired for {client_ip}:{client_port}")
            return None

        return session

    def get_session_by_token(self, token: str) -> Optional[ActiveSession]:
        """
        Get session by token

        Args:
            token: Authentication token

        Returns:
            ActiveSession if found and valid, None otherwise
        """
        session = self.sessions_by_token.get(token)

        if not session:
            return None

        if session.is_expired():
            return None

        return session

    async def update_activity(
        self,
        client_ip: str,
        client_port: int
    ):
        """
        Update session activity timestamp

        Args:
            client_ip: Client IP
            client_port: Client port
        """
        session = self.get_session_by_client(client_ip, client_port)

        if session:
            session.update_activity()

            # Periodically sync to database (every 10 seconds)
            if (datetime.utcnow() - session.last_activity).total_seconds() > 10:
                await self.db.update_session_activity(session.session_id)

    def assign_radio(
        self,
        client_ip: str,
        client_port: int,
        radio_ip: str,
        radio_port: int,
        radio_id: Optional[int] = None
    ) -> bool:
        """
        Assign radio to session

        Args:
            client_ip: Client IP
            client_port: Client port
            radio_ip: Radio IP
            radio_port: Radio port
            radio_id: Radio ID

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session_by_client(client_ip, client_port)

        if not session:
            return False

        session.radio_address = (radio_ip, radio_port)
        session.radio_id = radio_id

        self.logger.info(
            f"Assigned radio {radio_ip}:{radio_port} to client {client_ip}:{client_port}"
        )

        return True

    def get_radio_for_client(
        self,
        client_ip: str,
        client_port: int
    ) -> Optional[Tuple[str, int]]:
        """
        Get assigned radio address for client

        Args:
            client_ip: Client IP
            client_port: Client port

        Returns:
            Radio address (IP, port) or None
        """
        session = self.get_session_by_client(client_ip, client_port)

        if session:
            return session.radio_address

        return None

    def get_client_for_radio(
        self,
        radio_ip: str,
        radio_port: int
    ) -> Optional[Tuple[str, int]]:
        """
        Get client address that is connected to a radio

        Args:
            radio_ip: Radio IP
            radio_port: Radio port

        Returns:
            Client address (IP, port) or None
        """
        radio_address = (radio_ip, radio_port)

        for session in self.sessions_by_client.values():
            if session.radio_address == radio_address:
                return session.client_address

        return None

    async def terminate_session(
        self,
        client_ip: str,
        client_port: int,
        reason: str = "terminated"
    ):
        """
        Terminate a session

        Args:
            client_ip: Client IP
            client_port: Client port
            reason: Termination reason
        """
        session = self.get_session_by_client(client_ip, client_port)

        if not session:
            return

        # Deactivate in database
        await self.db.deactivate_session(session.session_id)

        # Log activity
        await self.db.log_activity(
            action="session_terminated",
            user_id=session.user_id,
            session_id=session.session_id,
            description=f"Session terminated: {reason}",
            ip_address=client_ip
        )

        # Remove from memory
        self._remove_session(session)

        self.logger.info(
            f"Session terminated for {session.username} "
            f"from {client_ip}:{client_port} (reason: {reason})"
        )

    async def _cleanup_loop(self):
        """Background task to cleanup expired/idle sessions"""
        self.logger.info("Session cleanup task started")

        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_sessions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

        self.logger.info("Session cleanup task stopped")

    async def _cleanup_sessions(self):
        """Clean up expired and idle sessions"""
        now = datetime.utcnow()
        expired = []
        idle = []

        # Find expired and idle sessions
        for session in list(self.sessions_by_client.values()):
            if session.is_expired():
                expired.append(session)
            elif session.is_idle(self.session_timeout):
                idle.append(session)

        # Clean up expired sessions
        for session in expired:
            await self.terminate_session(
                session.client_address[0],
                session.client_address[1],
                "expired"
            )
            self.stats['expired_sessions'] += 1

        # Clean up idle sessions
        for session in idle:
            await self.terminate_session(
                session.client_address[0],
                session.client_address[1],
                "timeout"
            )
            self.stats['timeouts'] += 1

        # Cleanup database sessions
        await self.db.cleanup_expired_sessions()

        if expired or idle:
            self.logger.info(
                f"Cleaned up {len(expired)} expired and {len(idle)} idle sessions"
            )

    def get_all_sessions(self) -> List[ActiveSession]:
        """Get all active sessions"""
        return list(self.sessions_by_client.values())

    def get_session_count(self) -> int:
        """Get active session count"""
        return len(self.sessions_by_client)

    def get_statistics(self) -> Dict:
        """Get session statistics"""
        return {
            **self.stats,
            'active_sessions': len(self.sessions_by_client),
        }

    async def validate_client(
        self,
        client_ip: str,
        client_port: int,
        token: Optional[str] = None
    ) -> Tuple[bool, Optional[ActiveSession]]:
        """
        Validate if client has valid session

        Args:
            client_ip: Client IP
            client_port: Client port
            token: Optional authentication token

        Returns:
            Tuple of (is_valid, session)
        """
        # Try to get session by client address
        session = self.get_session_by_client(client_ip, client_port)

        if session:
            # Update activity
            session.update_activity()
            return True, session

        # If token provided, try to validate and create session
        if token:
            try:
                user = await self.auth.validate_token(token)
                if user:
                    # Get session from database
                    db_session = await self.db.get_session_by_token(token)
                    if db_session and db_session.active:
                        # Recreate in-memory session
                        expires_at = db_session.expires_at
                        await self.create_session(
                            user=user,
                            token=token,
                            client_ip=client_ip,
                            client_port=client_port,
                            expires_at=expires_at,
                            radio_id=db_session.radio_id
                        )
                        session = self.get_session_by_client(client_ip, client_port)
                        return True, session

            except Exception as e:
                self.logger.error(f"Error validating token: {e}")

        return False, None
