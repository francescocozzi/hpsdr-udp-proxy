"""
Authentication Manager for HPSDR Proxy

Handles JWT tokens, password hashing, and authentication logic.
"""
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from passlib.hash import bcrypt

from .db_manager import DatabaseManager
from .models import User, Session
from ..utils import get_logger, log_exceptions


class AuthenticationError(Exception):
    """Base exception for authentication errors"""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""
    pass


class AccountLockedError(AuthenticationError):
    """Account is locked"""
    pass


class TokenExpiredError(AuthenticationError):
    """Token has expired"""
    pass


class InvalidTokenError(AuthenticationError):
    """Token is invalid"""
    pass


class AuthManager:
    """
    Authentication manager handling JWT tokens and password hashing

    Features:
    - Password hashing with bcrypt
    - JWT token generation and validation
    - Login attempt tracking
    - Account lockout mechanism
    - Session management
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        token_expiry: int = 3600,
        refresh_token_expiry: int = 604800,
        max_login_attempts: int = 5,
        lockout_duration: int = 300
    ):
        """
        Initialize authentication manager

        Args:
            db_manager: Database manager instance
            jwt_secret: Secret key for JWT signing
            jwt_algorithm: JWT algorithm (default: HS256)
            token_expiry: Access token expiry in seconds (default: 1 hour)
            refresh_token_expiry: Refresh token expiry in seconds (default: 7 days)
            max_login_attempts: Maximum failed login attempts before lockout
            lockout_duration: Account lockout duration in seconds
        """
        self.db = db_manager
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.token_expiry = token_expiry
        self.refresh_token_expiry = refresh_token_expiry
        self.max_login_attempts = max_login_attempts
        self.lockout_duration = lockout_duration

        self.logger = get_logger(__name__)

    # ==================== Password Hashing ====================

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return bcrypt.hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash

        Args:
            password: Plain text password
            password_hash: Stored password hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.verify(password, password_hash)
        except Exception:
            return False

    # ==================== JWT Token Operations ====================

    def generate_token(
        self,
        user_id: int,
        username: str,
        is_admin: bool = False,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate JWT access token

        Args:
            user_id: User ID
            username: Username
            is_admin: Whether user is admin
            extra_claims: Additional claims to include

        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiry = now + timedelta(seconds=self.token_expiry)

        payload = {
            'user_id': user_id,
            'username': username,
            'is_admin': is_admin,
            'iat': now,
            'exp': expiry,
            'type': 'access'
        }

        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token

    def generate_refresh_token(
        self,
        user_id: int,
        username: str
    ) -> str:
        """
        Generate JWT refresh token

        Args:
            user_id: User ID
            username: Username

        Returns:
            JWT refresh token string
        """
        now = datetime.utcnow()
        expiry = now + timedelta(seconds=self.refresh_token_expiry)

        payload = {
            'user_id': user_id,
            'username': username,
            'iat': now,
            'exp': expiry,
            'type': 'refresh',
            'jti': secrets.token_urlsafe(32)  # Unique token ID
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token string

        Returns:
            Token payload dictionary

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            return payload

        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired")
            raise TokenExpiredError("Token has expired")

        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {e}")
            raise InvalidTokenError("Invalid token")

    def extract_user_from_token(self, token: str) -> Tuple[int, str]:
        """
        Extract user ID and username from token

        Args:
            token: JWT token string

        Returns:
            Tuple of (user_id, username)

        Raises:
            TokenExpiredError or InvalidTokenError
        """
        payload = self.verify_token(token)
        return payload['user_id'], payload['username']

    # ==================== Authentication ====================

    @log_exceptions(get_logger(__name__), reraise=True)
    async def authenticate(
        self,
        username: str,
        password: str,
        client_ip: str,
        client_port: int = 0
    ) -> Tuple[str, str, User]:
        """
        Authenticate user with username and password

        Args:
            username: Username
            password: Password
            client_ip: Client IP address
            client_port: Client port

        Returns:
            Tuple of (access_token, refresh_token, user)

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AccountLockedError: If account is locked
        """
        # Get user from database
        user = await self.db.get_user_by_username(username)

        if not user or not user.enabled:
            self.logger.warning(f"Login attempt for non-existent/disabled user: {username}")
            await self.db.log_activity(
                action="login_failed",
                description=f"Invalid username: {username}",
                ip_address=client_ip
            )
            raise InvalidCredentialsError("Invalid username or password")

        # Check if account is locked
        if user.is_locked():
            self.logger.warning(f"Login attempt for locked account: {username}")
            await self.db.log_activity(
                action="login_locked",
                user_id=user.id,
                description=f"Account locked until {user.locked_until}",
                ip_address=client_ip
            )
            raise AccountLockedError("Account is locked. Please try again later.")

        # Verify password
        if not self.verify_password(password, user.password_hash):
            # Increment failed login attempts
            failed_attempts = await self.db.increment_failed_login(user.id)
            self.logger.warning(
                f"Failed login attempt for {username} "
                f"(attempt {failed_attempts}/{self.max_login_attempts})"
            )

            # Lock account if max attempts reached
            if failed_attempts >= self.max_login_attempts:
                await self.db.lock_user(user.id, self.lockout_duration)
                self.logger.warning(f"Account {username} locked due to failed login attempts")
                await self.db.log_activity(
                    action="account_locked",
                    user_id=user.id,
                    description=f"Locked after {failed_attempts} failed attempts",
                    ip_address=client_ip
                )

            await self.db.log_activity(
                action="login_failed",
                user_id=user.id,
                description="Invalid password",
                ip_address=client_ip
            )

            raise InvalidCredentialsError("Invalid username or password")

        # Authentication successful
        # Reset failed login attempts
        await self.db.reset_failed_login(user.id)

        # Update last login
        await self.db.update_user(user.id, last_login=datetime.utcnow())

        # Generate tokens
        access_token = self.generate_token(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin
        )

        refresh_token = self.generate_refresh_token(
            user_id=user.id,
            username=user.username
        )

        # Create session in database
        expires_at = datetime.utcnow() + timedelta(seconds=self.token_expiry)
        await self.db.create_session(
            user_id=user.id,
            token=access_token,
            refresh_token=refresh_token,
            client_ip=client_ip,
            client_port=client_port,
            expires_at=expires_at
        )

        # Log successful login
        await self.db.log_activity(
            action="login_success",
            user_id=user.id,
            description=f"Successful login from {client_ip}",
            ip_address=client_ip
        )

        self.logger.info(f"User {username} authenticated successfully from {client_ip}")

        return access_token, refresh_token, user

    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Tuple[str, str]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            TokenExpiredError or InvalidTokenError
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token)

        if payload.get('type') != 'refresh':
            raise InvalidTokenError("Not a refresh token")

        user_id = payload['user_id']
        username = payload['username']

        # Get user from database
        user = await self.db.get_user_by_id(user_id)

        if not user or not user.enabled:
            raise InvalidCredentialsError("User not found or disabled")

        # Generate new tokens
        new_access_token = self.generate_token(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin
        )

        new_refresh_token = self.generate_refresh_token(
            user_id=user.id,
            username=user.username
        )

        self.logger.info(f"Refreshed tokens for user {username}")

        return new_access_token, new_refresh_token

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate token and return user

        Args:
            token: JWT token

        Returns:
            User object if valid, None otherwise
        """
        try:
            payload = self.verify_token(token)
            user_id = payload['user_id']

            # Get user from database
            user = await self.db.get_user_by_id(user_id)

            if not user or not user.enabled:
                return None

            return user

        except (TokenExpiredError, InvalidTokenError):
            return None

    async def logout(self, token: str):
        """
        Logout user by deactivating session

        Args:
            token: JWT token
        """
        try:
            # Get session from database
            session = await self.db.get_session_by_token(token)

            if session:
                await self.db.deactivate_session(session.id)

                await self.db.log_activity(
                    action="logout",
                    user_id=session.user_id,
                    session_id=session.id,
                    description="User logged out",
                    ip_address=session.client_ip
                )

                self.logger.info(f"User {session.user.username} logged out")

        except Exception as e:
            self.logger.error(f"Error during logout: {e}")

    # ==================== User Management ====================

    async def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """
        Create a new user

        Args:
            username: Username
            password: Plain text password
            email: Email address
            full_name: Full name
            is_admin: Whether user is admin

        Returns:
            Created user object

        Raises:
            ValueError: If username already exists
        """
        # Check if username exists
        existing_user = await self.db.get_user_by_username(username)
        if existing_user:
            raise ValueError(f"Username {username} already exists")

        # Check if email exists
        if email:
            existing_email = await self.db.get_user_by_email(email)
            if existing_email:
                raise ValueError(f"Email {email} already in use")

        # Hash password
        password_hash = self.hash_password(password)

        # Create user
        user = await self.db.create_user(
            username=username,
            password_hash=password_hash,
            email=email,
            full_name=full_name,
            is_admin=is_admin
        )

        await self.db.log_activity(
            action="user_created",
            user_id=user.id,
            description=f"User {username} created"
        )

        self.logger.info(f"User {username} created successfully")

        return user

    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password

        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password

        Returns:
            True if successful, False otherwise

        Raises:
            InvalidCredentialsError: If old password is incorrect
        """
        user = await self.db.get_user_by_id(user_id)

        if not user:
            return False

        # Verify old password
        if not self.verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect")

        # Hash new password
        new_password_hash = self.hash_password(new_password)

        # Update password
        await self.db.update_user(user_id, password_hash=new_password_hash)

        await self.db.log_activity(
            action="password_changed",
            user_id=user_id,
            description="Password changed successfully"
        )

        self.logger.info(f"Password changed for user ID {user_id}")

        return True

    async def reset_password(
        self,
        user_id: int,
        new_password: str
    ) -> bool:
        """
        Reset user password (admin function)

        Args:
            user_id: User ID
            new_password: New password

        Returns:
            True if successful, False otherwise
        """
        # Hash new password
        new_password_hash = self.hash_password(new_password)

        # Update password
        user = await self.db.update_user(user_id, password_hash=new_password_hash)

        if not user:
            return False

        await self.db.log_activity(
            action="password_reset",
            user_id=user_id,
            description="Password reset by administrator"
        )

        self.logger.info(f"Password reset for user ID {user_id}")

        return True
