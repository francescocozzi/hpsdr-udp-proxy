"""
Database models for VPN user management
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model for authentication and VPN access"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # VPN Configuration
    vpn_enabled = Column(Boolean, default=True, nullable=False)
    vpn_public_key = Column(String(44), unique=True, nullable=True)  # WireGuard public key
    vpn_private_key = Column(String(44), nullable=True)  # Encrypted private key
    vpn_ip_address = Column(String(15), unique=True, nullable=True)  # Assigned VPN IP
    vpn_config = Column(Text, nullable=True)  # Full WireGuard config for client

    # User status
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_vpn_connection = Column(DateTime(timezone=True), nullable=True)

    # Rate limiting / usage tracking
    connection_count = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}', vpn_enabled={self.vpn_enabled})>"


class VPNSession(Base):
    """Track active VPN sessions"""
    __tablename__ = "vpn_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)  # Foreign key to users
    username = Column(String(50), index=True, nullable=False)

    # Session info
    client_ip = Column(String(45), nullable=True)  # Real client IP (can be IPv6)
    vpn_ip = Column(String(15), nullable=False)  # Assigned VPN IP

    # Timestamps
    connected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Traffic stats
    bytes_sent = Column(Integer, default=0, nullable=False)
    bytes_received = Column(Integer, default=0, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<VPNSession(username='{self.username}', vpn_ip='{self.vpn_ip}', active={self.is_active})>"


class AuditLog(Base):
    """Audit log for security and troubleshooting"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Who/What/Where
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # login, logout, vpn_connect, etc.
    resource = Column(String(100), nullable=True)  # What was accessed

    # Details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(Text, nullable=True)  # JSON metadata (renamed to avoid SQLAlchemy conflict)

    def __repr__(self):
        return f"<AuditLog(username='{self.username}', action='{self.action}', success={self.success})>"
