"""
FastAPI REST API for user management and VPN configuration

Provides endpoints for:
- User registration and authentication
- VPN configuration generation
- User management (admin)
- Statistics and monitoring
"""
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vpn.models import Base, User, VPNSession, AuditLog
from src.vpn.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    validate_access_token
)
from src.vpn.wireguard_manager import WireGuardManager
from src.utils import get_logger
from src.config import config

# Initialize FastAPI
app = FastAPI(
    title="HPSDR VPN Gateway API",
    description="User management and VPN configuration API for HPSDR radio access",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logger
logger = get_logger(__name__)

# Database setup (from configuration)
DATABASE_URL = config.database_url
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# WireGuard manager (will be initialized on startup)
wg_manager: Optional[WireGuardManager] = None

# Security
security = HTTPBearer()


# ====================
# Pydantic Models (Request/Response)
# ====================

class UserRegister(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login request"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


class UserResponse(BaseModel):
    """User information response"""
    id: int
    username: str
    email: str
    vpn_enabled: bool
    vpn_ip_address: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    connection_count: int


class VPNConfigResponse(BaseModel):
    """VPN configuration response"""
    config: str
    vpn_ip: str
    server_endpoint: str
    qr_code: Optional[str] = None  # Future: QR code for mobile


class AdminUserUpdate(BaseModel):
    """Admin-only user update"""
    vpn_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


# ====================
# Dependencies
# ====================

async def get_db():
    """Database session dependency"""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    payload = validate_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Get user from database
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin privileges"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# ====================
# Startup/Shutdown Events
# ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    global wg_manager

    logger.info("Starting HPSDR VPN Gateway API...")

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

    # Initialize WireGuard manager
    wg_manager = WireGuardManager(
        interface=config.vpn_interface,
        server_port=config.vpn_server_port,
        server_address=config.vpn_server_address,
        public_endpoint=config.vpn_public_endpoint
    )
    logger.info(f"WireGuard manager initialized: {config.vpn_public_endpoint}:{config.vpn_server_port}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down HPSDR VPN Gateway API...")


# ====================
# Health Check
# ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "wireguard_interface_up": wg_manager.is_interface_up() if wg_manager else False
    }


# ====================
# Authentication Endpoints
# ====================

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user

    Creates a new user account with VPN access. The user will receive
    VPN credentials that can be retrieved after authentication.
    """
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Generate WireGuard keys
    private_key, public_key = wg_manager.generate_keypair()
    vpn_ip = wg_manager.get_next_available_ip()

    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        vpn_enabled=True,
        vpn_public_key=public_key,
        vpn_private_key=private_key,  # TODO: Encrypt in production
        vpn_ip_address=vpn_ip
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Add peer to WireGuard
    wg_manager.add_peer(
        public_key=public_key,
        allowed_ips=f"{vpn_ip}/32",
        comment=user_data.username
    )

    # Create audit log
    audit = AuditLog(
        user_id=new_user.id,
        username=new_user.username,
        action="user_registered",
        success=True
    )
    db.add(audit)
    await db.commit()

    logger.info(f"New user registered: {user_data.username}")

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        vpn_enabled=new_user.vpn_enabled,
        vpn_ip_address=new_user.vpn_ip_address,
        is_active=new_user.is_active,
        is_admin=new_user.is_admin,
        created_at=new_user.created_at,
        last_login=new_user.last_login,
        connection_count=new_user.connection_count
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Login and receive JWT tokens

    Returns access and refresh tokens for API authentication.
    """
    # Get user
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        # Create audit log for failed login
        if user:
            audit = AuditLog(
                user_id=user.id,
                username=user.username,
                action="login_failed",
                success=False,
                error_message="Invalid password"
            )
            db.add(audit)
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.username, "user_id": user.id})

    # Create audit log
    audit = AuditLog(
        user_id=user.id,
        username=user.username,
        action="login_success",
        success=True
    )
    db.add(audit)
    await db.commit()

    logger.info(f"User logged in: {user.username}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


# ====================
# User Endpoints
# ====================

@app.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        vpn_enabled=current_user.vpn_enabled,
        vpn_ip_address=current_user.vpn_ip_address,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        connection_count=current_user.connection_count
    )


@app.get("/users/me/vpn-config", response_model=VPNConfigResponse)
async def get_vpn_config(current_user: User = Depends(get_current_user)):
    """
    Get WireGuard VPN configuration

    Returns a ready-to-use WireGuard configuration file that can be
    imported into WireGuard clients.
    """
    if not current_user.vpn_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VPN access is disabled for this account"
        )

    # Generate client configuration
    server_public_key = wg_manager.get_server_public_key()

    if not server_public_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve server public key"
        )

    config = wg_manager.generate_client_config(
        username=current_user.username,
        client_private_key=current_user.vpn_private_key,
        client_ip=current_user.vpn_ip_address,
        server_public_key=server_public_key,
        allowed_ips="10.8.0.0/24"  # Only VPN subnet, not full tunnel
    )

    logger.info(f"VPN config requested by: {current_user.username}")

    return VPNConfigResponse(
        config=config,
        vpn_ip=current_user.vpn_ip_address,
        server_endpoint=f"{wg_manager.public_endpoint}:{wg_manager.server_port}"
    )


# ====================
# Admin Endpoints
# ====================

@app.get("/admin/users", response_model=List[UserResponse])
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """List all users (admin only)"""
    result = await db.execute(select(User))
    users = result.scalars().all()

    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            vpn_enabled=u.vpn_enabled,
            vpn_ip_address=u.vpn_ip_address,
            is_active=u.is_active,
            is_admin=u.is_admin,
            created_at=u.created_at,
            last_login=u.last_login,
            connection_count=u.connection_count
        )
        for u in users
    ]


@app.patch("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    updates: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Update user settings (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    if updates.vpn_enabled is not None:
        user.vpn_enabled = updates.vpn_enabled

        # Update WireGuard peer
        if updates.vpn_enabled:
            wg_manager.add_peer(
                public_key=user.vpn_public_key,
                allowed_ips=f"{user.vpn_ip_address}/32",
                comment=user.username
            )
        else:
            wg_manager.remove_peer(user.vpn_public_key)

    if updates.is_active is not None:
        user.is_active = updates.is_active

    if updates.is_admin is not None:
        user.is_admin = updates.is_admin

    await db.commit()

    logger.info(f"User {user.username} updated by admin {admin_user.username}")

    return {"message": "User updated successfully"}


@app.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Delete a user (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Remove from WireGuard
    wg_manager.remove_peer(user.vpn_public_key)

    # Release IP
    wg_manager.release_ip(user.vpn_ip_address)

    # Delete user
    await db.delete(user)
    await db.commit()

    logger.info(f"User {user.username} deleted by admin {admin_user.username}")

    return {"message": "User deleted successfully"}


@app.get("/admin/vpn/peers")
async def list_vpn_peers(admin_user: User = Depends(require_admin)):
    """List all connected VPN peers (admin only)"""
    peers = wg_manager.list_peers()
    return {"peers": peers, "count": len(peers)}


# ====================
# Statistics
# ====================

@app.get("/stats/system")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get system statistics"""
    # Count total users
    result = await db.execute(select(User))
    total_users = len(result.scalars().all())

    # Count active users
    result = await db.execute(select(User).where(User.is_active == True))
    active_users = len(result.scalars().all())

    # Get VPN peers
    peers = wg_manager.list_peers()
    connected_peers = len([p for p in peers if p.get('latest_handshake')])

    return {
        "total_users": total_users,
        "active_users": active_users,
        "connected_peers": connected_peers,
        "vpn_interface_up": wg_manager.is_interface_up()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.api_host, port=config.api_port)
