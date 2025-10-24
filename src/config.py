"""
Configuration Manager

Handles loading and validating configuration from file or environment variables.
"""
import os
import configparser
from pathlib import Path
from typing import Optional


class Config:
    """Application configuration"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration

        Args:
            config_file: Path to config file (defaults to config.ini)
        """
        self.config = configparser.ConfigParser()

        # Default config file path
        if config_file is None:
            config_file = os.getenv('VPN_CONFIG_FILE', 'config.ini')

        config_path = Path(config_file)

        # Load config file if it exists
        if config_path.exists():
            self.config.read(config_path)

        # Set defaults
        self._set_defaults()

    def _set_defaults(self):
        """Set default configuration values"""
        if 'vpn' not in self.config:
            self.config['vpn'] = {}
        if 'api' not in self.config:
            self.config['api'] = {}
        if 'database' not in self.config:
            self.config['database'] = {}
        if 'security' not in self.config:
            self.config['security'] = {}
        if 'logging' not in self.config:
            self.config['logging'] = {}

    def get(self, section: str, key: str, fallback: str = '') -> str:
        """
        Get configuration value with environment variable override

        Priority: Environment Variable > Config File > Fallback

        Args:
            section: Config section
            key: Config key
            fallback: Default value if not found

        Returns:
            Configuration value
        """
        # Environment variable format: VPN_SECTION_KEY
        env_key = f"VPN_{section.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)

        if env_value is not None:
            return env_value

        return self.config.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(section, key, str(fallback))
        try:
            return int(value)
        except ValueError:
            return fallback

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(section, key, str(fallback))
        return value.lower() in ('true', 'yes', '1', 'on')

    # VPN Configuration
    @property
    def vpn_public_endpoint(self) -> str:
        """VPN server public endpoint (IP or hostname)"""
        return self.get('vpn', 'public_endpoint', '127.0.0.1')

    @property
    def vpn_server_port(self) -> int:
        """VPN server port"""
        return self.getint('vpn', 'server_port', 51820)

    @property
    def vpn_server_address(self) -> str:
        """VPN server address with netmask"""
        return self.get('vpn', 'server_address', '10.8.0.1/24')

    @property
    def vpn_interface(self) -> str:
        """WireGuard interface name"""
        return self.get('vpn', 'interface', 'wg0')

    # API Configuration
    @property
    def api_host(self) -> str:
        """API server host"""
        return self.get('api', 'host', '0.0.0.0')

    @property
    def api_port(self) -> int:
        """API server port"""
        return self.getint('api', 'port', 8000)

    @property
    def jwt_secret(self) -> str:
        """JWT secret key"""
        return self.get('api', 'jwt_secret', 'INSECURE-CHANGE-ME')

    @property
    def jwt_algorithm(self) -> str:
        """JWT algorithm"""
        return self.get('api', 'jwt_algorithm', 'HS256')

    @property
    def access_token_expire_minutes(self) -> int:
        """Access token expiration in minutes"""
        return self.getint('api', 'access_token_expire_minutes', 30)

    # Database Configuration
    @property
    def database_url(self) -> str:
        """Database connection URL"""
        return self.get('database', 'url', 'sqlite:///./vpn_gateway.db')

    # Security Configuration
    @property
    def password_min_length(self) -> int:
        """Minimum password length"""
        return self.getint('security', 'password_min_length', 8)

    @property
    def require_email_verification(self) -> bool:
        """Require email verification"""
        return self.getboolean('security', 'require_email_verification', False)

    @property
    def max_login_attempts(self) -> int:
        """Maximum login attempts before lockout"""
        return self.getint('security', 'max_login_attempts', 5)

    @property
    def lockout_duration_minutes(self) -> int:
        """Account lockout duration in minutes"""
        return self.getint('security', 'lockout_duration_minutes', 15)

    # Logging Configuration
    @property
    def log_level(self) -> str:
        """Logging level"""
        return self.get('logging', 'level', 'INFO')

    @property
    def log_file(self) -> str:
        """Log file path"""
        return self.get('logging', 'file', 'vpn_gateway.log')


# Global config instance
config = Config()
