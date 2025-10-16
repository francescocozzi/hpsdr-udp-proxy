"""
Database Manager for HPSDR Proxy

Handles all database operations using async SQLAlchemy.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy import select, delete, update, and_, or_, func
from sqlalchemy.orm import selectinload

from .models import Base, User, Radio, Session, TimeSlot, ActivityLog, Statistics, APIKey
from ..utils import get_logger, log_exceptions


class DatabaseManager:
    """
    Async database manager for all database operations

    Provides CRUD operations and query methods for all models.
    Uses connection pooling for performance.
    """

    def __init__(self, connection_string: str, pool_size: int = 10, max_overflow: int = 20):
        """
        Initialize database manager

        Args:
            connection_string: SQLAlchemy connection string
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        self.connection_string = connection_string
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.logger = get_logger(__name__)

        self.pool_size = pool_size
        self.max_overflow = max_overflow

    async def connect(self):
        """Establish database connection and create session factory"""
        if self.engine:
            self.logger.warning("Database already connected")
            return

        self.logger.info(f"Connecting to database...")

        self.engine = create_async_engine(
            self.connection_string,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,  # Verify connections before using
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        self.logger.info("Database connected successfully")

    async def disconnect(self):
        """Close database connection"""
        if not self.engine:
            return

        self.logger.info("Closing database connection...")
        await self.engine.dispose()
        self.engine = None
        self.session_factory = None
        self.logger.info("Database connection closed")

    @asynccontextmanager
    async def session(self):
        """
        Async context manager for database sessions

        Usage:
            async with db_manager.session() as session:
                result = await session.execute(...)
        """
        if not self.session_factory:
            raise RuntimeError("Database not connected. Call connect() first.")

        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            self.logger.error(f"Database transaction error: {e}")
            raise
        finally:
            await session.close()

    # ==================== User Operations ====================

    @log_exceptions(get_logger(__name__))
    async def create_user(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """Create a new user"""
        async with self.session() as session:
            user = User(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                is_admin=is_admin
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        async with self.session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        async with self.session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()

    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user fields"""
        async with self.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await session.flush()
            await session.refresh(user)
            return user

    async def delete_user(self, user_id: int) -> bool:
        """Delete user"""
        async with self.session() as session:
            result = await session.execute(
                delete(User).where(User.id == user_id)
            )
            return result.rowcount > 0

    async def list_users(
        self,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """List users with pagination"""
        async with self.session() as session:
            query = select(User)

            if enabled_only:
                query = query.where(User.enabled == True)

            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def increment_failed_login(self, user_id: int) -> int:
        """Increment failed login attempts"""
        async with self.session() as session:
            result = await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(failed_login_attempts=User.failed_login_attempts + 1)
                .returning(User.failed_login_attempts)
            )
            return result.scalar_one()

    async def reset_failed_login(self, user_id: int):
        """Reset failed login attempts"""
        await self.update_user(user_id, failed_login_attempts=0, locked_until=None)

    async def lock_user(self, user_id: int, duration_seconds: int):
        """Lock user account for specified duration"""
        locked_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        await self.update_user(user_id, locked_until=locked_until)

    # ==================== Radio Operations ====================

    async def create_radio(
        self,
        name: str,
        ip_address: str,
        port: int = 1024,
        mac_address: Optional[str] = None,
        description: Optional[str] = None,
        enabled: bool = True
    ) -> Radio:
        """Create a new radio"""
        async with self.session() as session:
            radio = Radio(
                name=name,
                ip_address=ip_address,
                port=port,
                mac_address=mac_address,
                description=description,
                enabled=enabled
            )
            session.add(radio)
            await session.flush()
            await session.refresh(radio)
            return radio

    async def get_radio_by_id(self, radio_id: int) -> Optional[Radio]:
        """Get radio by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(Radio).where(Radio.id == radio_id)
            )
            return result.scalar_one_or_none()

    async def get_radio_by_ip(self, ip_address: str) -> Optional[Radio]:
        """Get radio by IP address"""
        async with self.session() as session:
            result = await session.execute(
                select(Radio).where(Radio.ip_address == ip_address)
            )
            return result.scalar_one_or_none()

    async def list_radios(self, enabled_only: bool = False) -> List[Radio]:
        """List all radios"""
        async with self.session() as session:
            query = select(Radio)

            if enabled_only:
                query = query.where(Radio.enabled == True)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_radio(self, radio_id: int, **kwargs) -> Optional[Radio]:
        """Update radio fields"""
        async with self.session() as session:
            result = await session.execute(
                select(Radio).where(Radio.id == radio_id)
            )
            radio = result.scalar_one_or_none()

            if not radio:
                return None

            for key, value in kwargs.items():
                if hasattr(radio, key):
                    setattr(radio, key, value)

            await session.flush()
            await session.refresh(radio)
            return radio

    async def delete_radio(self, radio_id: int) -> bool:
        """Delete radio"""
        async with self.session() as session:
            result = await session.execute(
                delete(Radio).where(Radio.id == radio_id)
            )
            return result.rowcount > 0

    # ==================== Session Operations ====================

    async def create_session(
        self,
        user_id: int,
        token: str,
        client_ip: str,
        client_port: int,
        expires_at: datetime,
        radio_id: Optional[int] = None,
        refresh_token: Optional[str] = None
    ) -> Session:
        """Create a new session"""
        async with self.session() as session:
            sess = Session(
                user_id=user_id,
                token=token,
                refresh_token=refresh_token,
                client_ip=client_ip,
                client_port=client_port,
                radio_id=radio_id,
                expires_at=expires_at
            )
            session.add(sess)
            await session.flush()
            await session.refresh(sess)
            return sess

    async def get_session_by_token(self, token: str) -> Optional[Session]:
        """Get session by token"""
        async with self.session() as session:
            result = await session.execute(
                select(Session)
                .where(Session.token == token)
                .options(selectinload(Session.user), selectinload(Session.radio))
            )
            return result.scalar_one_or_none()

    async def get_session_by_client(
        self,
        client_ip: str,
        client_port: int
    ) -> Optional[Session]:
        """Get active session by client address"""
        async with self.session() as session:
            now = datetime.utcnow()
            result = await session.execute(
                select(Session)
                .where(
                    and_(
                        Session.client_ip == client_ip,
                        Session.client_port == client_port,
                        Session.active == True,
                        Session.expires_at > now
                    )
                )
                .options(selectinload(Session.user), selectinload(Session.radio))
            )
            return result.scalar_one_or_none()

    async def update_session_activity(self, session_id: int):
        """Update last activity timestamp"""
        async with self.session() as session:
            await session.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(last_activity=datetime.utcnow())
            )

    async def deactivate_session(self, session_id: int):
        """Deactivate a session"""
        async with self.session() as session:
            await session.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(active=False)
            )

    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        async with self.session() as session:
            now = datetime.utcnow()
            result = await session.execute(
                delete(Session).where(Session.expires_at < now)
            )
            count = result.rowcount
            self.logger.info(f"Cleaned up {count} expired sessions")
            return count

    async def list_active_sessions(self) -> List[Session]:
        """List all active sessions"""
        async with self.session() as session:
            now = datetime.utcnow()
            result = await session.execute(
                select(Session)
                .where(
                    and_(
                        Session.active == True,
                        Session.expires_at > now
                    )
                )
                .options(selectinload(Session.user), selectinload(Session.radio))
            )
            return list(result.scalars().all())

    # ==================== Activity Log Operations ====================

    async def log_activity(
        self,
        action: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ActivityLog:
        """Log an activity"""
        async with self.session() as session:
            log = ActivityLog(
                user_id=user_id,
                session_id=session_id,
                action=action,
                description=description,
                ip_address=ip_address,
                metadata=metadata
            )
            session.add(log)
            await session.flush()
            await session.refresh(log)
            return log

    async def get_activity_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ActivityLog]:
        """Get activity logs with filters"""
        async with self.session() as session:
            query = select(ActivityLog)

            if user_id:
                query = query.where(ActivityLog.user_id == user_id)
            if action:
                query = query.where(ActivityLog.action == action)

            query = query.order_by(ActivityLog.timestamp.desc()).limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    # ==================== Statistics Operations ====================

    async def record_statistics(
        self,
        radio_id: Optional[int] = None,
        session_id: Optional[int] = None,
        packets_received: int = 0,
        packets_sent: int = 0,
        bytes_received: int = 0,
        bytes_sent: int = 0,
        errors_count: int = 0,
        average_latency_ms: Optional[float] = None,
        interval_seconds: int = 60
    ) -> Statistics:
        """Record statistics"""
        async with self.session() as session:
            stats = Statistics(
                radio_id=radio_id,
                session_id=session_id,
                packets_received=packets_received,
                packets_sent=packets_sent,
                bytes_received=bytes_received,
                bytes_sent=bytes_sent,
                errors_count=errors_count,
                average_latency_ms=average_latency_ms,
                interval_seconds=interval_seconds
            )
            session.add(stats)
            await session.flush()
            await session.refresh(stats)
            return stats

    async def get_statistics(
        self,
        radio_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Statistics]:
        """Get statistics with filters"""
        async with self.session() as session:
            query = select(Statistics)

            if radio_id:
                query = query.where(Statistics.radio_id == radio_id)
            if since:
                query = query.where(Statistics.timestamp >= since)

            query = query.order_by(Statistics.timestamp.desc()).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            async with self.session() as session:
                await session.execute(select(1))
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
