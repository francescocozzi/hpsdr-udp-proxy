"""
Configuration management for HPSDR Proxy
"""
import os
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class ProxyConfig(BaseModel):
    """Proxy server configuration"""
    listen_address: str = "0.0.0.0"
    listen_port: int = 1024
    buffer_size: int = 2048
    session_timeout: int = 60
    max_sessions: int = 50


class DatabaseConfig(BaseModel):
    """Database configuration"""
    type: str = "postgresql"  # postgresql or sqlite
    host: str = "localhost"
    port: int = 5432
    name: str = "hpsdr_proxy"
    user: str = "proxy_user"
    password: str = ""
    sqlite_path: str = "database/proxy.db"
    pool_size: int = 10
    max_overflow: int = 20

    @validator("type")
    def validate_db_type(cls, v):
        if v not in ["postgresql", "sqlite"]:
            raise ValueError("Database type must be 'postgresql' or 'sqlite'")
        return v

    def get_connection_string(self) -> str:
        """Get SQLAlchemy connection string"""
        if self.type == "sqlite":
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        else:
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RadioConfig(BaseModel):
    """Radio configuration"""
    name: str
    ip: str
    port: int = 1024  # Discovery/control port
    data_port: Optional[int] = None  # Data streaming port (HPSDR Protocol 1, typically 1025)
    mac: Optional[str] = None
    enabled: bool = True
    description: Optional[str] = None

    def get_data_port(self) -> int:
        """Get data port, defaulting to port if not specified"""
        return self.data_port if self.data_port is not None else self.port


class AuthConfig(BaseModel):
    """Authentication configuration"""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    token_expiry: int = 3600  # seconds
    refresh_token_expiry: int = 604800  # 7 days
    max_login_attempts: int = 5
    lockout_duration: int = 300  # seconds


class APIConfig(BaseModel):
    """REST API configuration"""
    host: str = "0.0.0.0"
    port: int = 8080
    cors_enabled: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    file: str = "logs/proxy.log"
    max_file_size: int = 10  # MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    json_format: bool = False
    console_enabled: bool = True

    @validator("level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()


class PerformanceConfig(BaseModel):
    """Performance configuration"""
    worker_threads: int = 4
    stats_enabled: bool = True
    stats_interval: int = 30  # seconds
    monitoring_enabled: bool = True


class SecurityConfig(BaseModel):
    """Security configuration"""
    ip_whitelist_enabled: bool = False
    allowed_ips: List[str] = []
    ip_blacklist_enabled: bool = False
    blocked_ips: List[str] = []
    require_authentication: bool = True
    allow_anonymous_discovery: bool = False


class TimeSlotConfig(BaseModel):
    """Time slot reservation configuration"""
    enabled: bool = True
    min_duration: int = 15  # minutes
    max_duration: int = 240  # minutes (4 hours)
    max_advance_days: int = 30
    grace_period: int = 5  # minutes


class Config(BaseSettings):
    """Main configuration class"""
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    radios: List[RadioConfig] = Field(default_factory=list)
    auth: AuthConfig
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    timeslots: TimeSlotConfig = Field(default_factory=TimeSlotConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"

    @classmethod
    def load_from_yaml(cls, config_path: str) -> "Config":
        """Load configuration from YAML file"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, "r") as f:
            config_dict = yaml.safe_load(f)

        return cls(**config_dict)

    @classmethod
    def load_from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls()

    def save_to_yaml(self, config_path: str):
        """Save configuration to YAML file"""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = self.model_dump()
        with open(path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)

    def get_radio_by_name(self, name: str) -> Optional[RadioConfig]:
        """Get radio configuration by name"""
        for radio in self.radios:
            if radio.name == name:
                return radio
        return None

    def get_enabled_radios(self) -> List[RadioConfig]:
        """Get all enabled radios"""
        return [radio for radio in self.radios if radio.enabled]


# Global configuration instance
_config: Optional[Config] = None


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment

    Args:
        config_path: Path to YAML configuration file. If None, loads from environment.

    Returns:
        Config instance
    """
    global _config

    if config_path:
        _config = Config.load_from_yaml(config_path)
    else:
        # Try to find config.yaml in standard locations
        search_paths = [
            "config/config.yaml",
            "config.yaml",
            "../config/config.yaml",
        ]

        for path in search_paths:
            if Path(path).exists():
                _config = Config.load_from_yaml(path)
                return _config

        # Fall back to environment variables
        _config = Config.load_from_env()

    return _config


def get_config() -> Config:
    """
    Get the global configuration instance

    Returns:
        Config instance

    Raises:
        RuntimeError: If configuration has not been loaded
    """
    if _config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return _config


def reload_config(config_path: Optional[str] = None) -> Config:
    """
    Reload configuration

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Config instance
    """
    return load_config(config_path)
