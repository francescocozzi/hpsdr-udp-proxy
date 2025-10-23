"""
WireGuard VPN Manager

Handles WireGuard configuration, key generation, and peer management.
"""
import subprocess
import ipaddress
import secrets
from typing import Optional, Tuple, List
from pathlib import Path
from ..utils import get_logger


class WireGuardManager:
    """Manages WireGuard VPN server configuration and client peers"""

    def __init__(
        self,
        config_path: str = "/etc/wireguard/wg0.conf",
        interface: str = "wg0",
        server_port: int = 51820,
        server_address: str = "10.8.0.1/24",
        public_endpoint: Optional[str] = None
    ):
        """
        Initialize WireGuard manager

        Args:
            config_path: Path to WireGuard config file
            interface: Network interface name
            server_port: UDP port for WireGuard
            server_address: Server VPN IP address with netmask
            public_endpoint: Public IP/hostname for clients to connect
        """
        self.logger = get_logger(__name__)
        self.config_path = Path(config_path)
        self.interface = interface
        self.server_port = server_port
        self.server_address = server_address
        self.public_endpoint = public_endpoint

        # Parse server network
        self.network = ipaddress.IPv4Network(server_address, strict=False)
        self.server_ip = str(self.network.network_address + 1)  # .1 is server

        # Track assigned IPs
        self.assigned_ips = set([self.server_ip])

        self.logger.info(f"WireGuard manager initialized: {self.interface} on {self.server_address}")

    def generate_keypair(self) -> Tuple[str, str]:
        """
        Generate WireGuard key pair

        Returns:
            Tuple of (private_key, public_key)
        """
        try:
            # Generate private key
            private_result = subprocess.run(
                ["sudo", "wg", "genkey"],
                capture_output=True,
                text=True,
                check=True
            )
            private_key = private_result.stdout.strip()

            # Generate public key from private key
            public_result = subprocess.run(
                ["sudo", "wg", "pubkey"],
                input=private_key,
                capture_output=True,
                text=True,
                check=True
            )
            public_key = public_result.stdout.strip()

            self.logger.debug(f"Generated WireGuard keypair")
            return private_key, public_key

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate WireGuard keys: {e}")
            raise

    def get_next_available_ip(self) -> str:
        """
        Get next available IP address in the VPN subnet

        Returns:
            Available IP address as string
        """
        for ip in self.network.hosts():
            ip_str = str(ip)
            if ip_str not in self.assigned_ips and ip_str != self.server_ip:
                self.assigned_ips.add(ip_str)
                return ip_str

        raise ValueError("No available IP addresses in VPN subnet")

    def release_ip(self, ip_address: str):
        """Release an IP address back to the pool"""
        if ip_address in self.assigned_ips and ip_address != self.server_ip:
            self.assigned_ips.discard(ip_address)

    def generate_client_config(
        self,
        username: str,
        client_private_key: str,
        client_ip: str,
        server_public_key: str,
        allowed_ips: str = "10.8.0.0/24"
    ) -> str:
        """
        Generate WireGuard client configuration

        Args:
            username: Username for comment
            client_private_key: Client's private key
            client_ip: Assigned VPN IP for client
            server_public_key: Server's public key
            allowed_ips: Networks accessible through VPN

        Returns:
            WireGuard configuration file content
        """
        config = f"""[Interface]
# Client configuration for {username}
PrivateKey = {client_private_key}
Address = {client_ip}/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
# Server
PublicKey = {server_public_key}
Endpoint = {self.public_endpoint}:{self.server_port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
"""
        return config

    def add_peer(
        self,
        public_key: str,
        allowed_ips: str,
        comment: Optional[str] = None
    ) -> bool:
        """
        Add a peer to the WireGuard interface

        Args:
            public_key: Client's public key
            allowed_ips: IPs allowed for this peer (typically their VPN IP)
            comment: Optional comment for logging

        Returns:
            True if successful
        """
        try:
            cmd = [
                "sudo", "wg", "set", self.interface,
                "peer", public_key,
                "allowed-ips", allowed_ips
            ]

            subprocess.run(cmd, check=True, capture_output=True)

            comment_str = f" ({comment})" if comment else ""
            self.logger.info(f"Added WireGuard peer{comment_str}: {public_key[:16]}...")

            # Save configuration
            self._save_config()

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to add WireGuard peer: {e}")
            return False

    def remove_peer(self, public_key: str) -> bool:
        """
        Remove a peer from the WireGuard interface

        Args:
            public_key: Client's public key

        Returns:
            True if successful
        """
        try:
            cmd = ["sudo", "wg", "set", self.interface, "peer", public_key, "remove"]
            subprocess.run(cmd, check=True, capture_output=True)

            self.logger.info(f"Removed WireGuard peer: {public_key[:16]}...")

            # Save configuration
            self._save_config()

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to remove WireGuard peer: {e}")
            return False

    def get_peer_stats(self, public_key: str) -> Optional[dict]:
        """
        Get statistics for a specific peer

        Args:
            public_key: Client's public key

        Returns:
            Dictionary with peer stats or None
        """
        try:
            result = subprocess.run(
                ["sudo", "wg", "show", self.interface, "dump"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.split('\t')
                if len(parts) >= 6 and parts[0] == public_key:
                    return {
                        'public_key': parts[0],
                        'preshared_key': parts[1],
                        'endpoint': parts[2] if parts[2] != '(none)' else None,
                        'allowed_ips': parts[3].split(','),
                        'latest_handshake': int(parts[4]) if parts[4] != '0' else None,
                        'bytes_received': int(parts[5]),
                        'bytes_sent': int(parts[6]) if len(parts) > 6 else 0,
                        'keepalive': int(parts[7]) if len(parts) > 7 and parts[7] != 'off' else None
                    }

            return None

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get peer stats: {e}")
            return None

    def list_peers(self) -> List[dict]:
        """
        List all connected peers

        Returns:
            List of peer dictionaries
        """
        try:
            result = subprocess.run(
                ["sudo", "wg", "show", self.interface, "dump"],
                capture_output=True,
                text=True,
                check=True
            )

            peers = []
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.split('\t')
                if len(parts) >= 6:
                    peers.append({
                        'public_key': parts[0],
                        'endpoint': parts[2] if parts[2] != '(none)' else None,
                        'allowed_ips': parts[3].split(','),
                        'latest_handshake': int(parts[4]) if parts[4] != '0' else None,
                        'bytes_received': int(parts[5]),
                        'bytes_sent': int(parts[6]) if len(parts) > 6 else 0,
                    })

            return peers

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to list peers: {e}")
            return []

    def _save_config(self):
        """Save current WireGuard configuration to disk"""
        try:
            subprocess.run(
                ["sudo", "wg-quick", "save", self.interface],
                check=True,
                capture_output=True
            )
            self.logger.debug("WireGuard configuration saved")

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to save WireGuard config: {e}")

    def get_server_public_key(self) -> Optional[str]:
        """
        Get the server's public key

        Returns:
            Server's public key or None
        """
        try:
            result = subprocess.run(
                ["sudo", "wg", "show", self.interface, "public-key"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get server public key: {e}")
            return None

    def is_interface_up(self) -> bool:
        """Check if WireGuard interface is up"""
        try:
            result = subprocess.run(
                ["sudo", "wg", "show", self.interface],
                capture_output=True,
                check=False
            )
            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to check interface status: {e}")
            return False
