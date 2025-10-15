"""
SQLAlchemy models for HPSDR Proxy database
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime,
    ForeignKey, CheckConstraint, BigInteger, Float, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True)
    full_name = Column(String(100))
    enabled = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    time_slots = relationship("TimeSlot", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', enabled={self.enabled})>"

    def is_locked(self) -> bool:
        """Check if user account is locked"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding password)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'enabled': self.enabled,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class Radio(Base):
    """Radio model"""
    __tablename__ = 'radios'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False)
    port = Column(Integer, default=1024)
    mac_address = Column(String(17))
    description = Column(Text)
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    sessions = relationship("Session", back_populates="radio")
    time_slots = relationship("TimeSlot", back_populates="radio", cascade="all, delete-orphan")
    statistics = relationship("Statistics", back_populates="radio", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Radio(id={self.id}, name='{self.name}', ip='{self.ip_address}', enabled={self.enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'ip_address': self.ip_address,
            'port': self.port,
            'mac_address': self.mac_address,
            'description': self.description,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Session(Base):
    """Session model"""
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    radio_id = Column(Integer, ForeignKey('radios.id', ondelete='SET NULL'), index=True)
    token = Column(String(512), unique=True, nullable=False, index=True)
    refresh_token = Column(String(512), unique=True)
    client_ip = Column(String(45), nullable=False, index=True)
    client_port = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False, index=True)
    last_activity = Column(DateTime, default=func.now())
    active = Column(Boolean, default=True, index=True)
    user_agent = Column(Text)

    # Relationships
    user = relationship("User", back_populates="sessions")
    radio = relationship("Radio", back_populates="sessions")
    statistics = relationship("Statistics", back_populates="session")
    activity_logs = relationship("ActivityLog", back_populates="session")

    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, active={self.active})>"

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if session is valid (active and not expired)"""
        return self.active and not self.is_expired()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'radio_id': self.radio_id,
            'client_ip': self.client_ip,
            'client_port': self.client_port,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'active': self.active,
        }


class TimeSlot(Base):
    """Time slot reservation model"""
    __tablename__ = 'time_slots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    radio_id = Column(Integer, ForeignKey('radios.id', ondelete='CASCADE'), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default='reserved', index=True)  # reserved, active, completed, cancelled
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint('end_time > start_time', name='valid_time_range'),
        CheckConstraint("status IN ('reserved', 'active', 'completed', 'cancelled')", name='valid_status'),
    )

    # Relationships
    user = relationship("User", back_populates="time_slots")
    radio = relationship("Radio", back_populates="time_slots")

    def __repr__(self):
        return f"<TimeSlot(id={self.id}, user_id={self.user_id}, radio_id={self.radio_id}, status='{self.status}')>"

    def is_active(self) -> bool:
        """Check if time slot is currently active"""
        now = datetime.utcnow()
        return self.start_time <= now <= self.end_time and self.status == 'active'

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'radio_id': self.radio_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ActivityLog(Base):
    """Activity log model"""
    __tablename__ = 'activity_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    action = Column(String(50), nullable=False, index=True)
    description = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=func.now(), index=True)
    metadata = Column(JSON)

    # Relationships
    user = relationship("User", back_populates="activity_logs")
    session = relationship("Session", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, action='{self.action}', timestamp={self.timestamp})>"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'action': self.action,
            'description': self.description,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata,
        }


class Statistics(Base):
    """Statistics model"""
    __tablename__ = 'statistics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    radio_id = Column(Integer, ForeignKey('radios.id', ondelete='CASCADE'), index=True)
    session_id = Column(Integer, ForeignKey('sessions.id', ondelete='SET NULL'), index=True)
    packets_received = Column(BigInteger, default=0)
    packets_sent = Column(BigInteger, default=0)
    bytes_received = Column(BigInteger, default=0)
    bytes_sent = Column(BigInteger, default=0)
    errors_count = Column(Integer, default=0)
    average_latency_ms = Column(Float)
    timestamp = Column(DateTime, default=func.now(), index=True)
    interval_seconds = Column(Integer, default=60)

    # Relationships
    radio = relationship("Radio", back_populates="statistics")
    session = relationship("Session", back_populates="statistics")

    def __repr__(self):
        return f"<Statistics(id={self.id}, radio_id={self.radio_id}, timestamp={self.timestamp})>"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'radio_id': self.radio_id,
            'session_id': self.session_id,
            'packets_received': self.packets_received,
            'packets_sent': self.packets_sent,
            'bytes_received': self.bytes_received,
            'bytes_sent': self.bytes_sent,
            'errors_count': self.errors_count,
            'average_latency_ms': self.average_latency_ms,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'interval_seconds': self.interval_seconds,
        }


class APIKey(Base):
    """API key model"""
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100))
    enabled = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    last_used = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    def is_expired(self) -> bool:
        """Check if API key is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if API key is valid"""
        return self.enabled and not self.is_expired()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'enabled': self.enabled,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
        }
