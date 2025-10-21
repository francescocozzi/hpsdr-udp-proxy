# HPSDR VPN Gateway Setup Guide

## Overview

This guide explains how to set up the HPSDR VPN Gateway, which provides secure authenticated access to remote HPSDR radios via WireGuard VPN.

## Architecture

```
[SDR Client] <--WireGuard VPN--> [Gateway Server] <---> [Hermes-Lite 2 Radio]
                                        |
                                  [Auth System]
                                  [User Management]
```

**Key Features:**
- ✅ User authentication (username/password)
- ✅ Automatic VPN configuration generation
- ✅ WireGuard VPN for secure, fast connections
- ✅ REST API for user management
- ✅ Admin panel for user administration
- ✅ Audit logging for security
- ✅ Full protocol compatibility (no packet modification)

## Prerequisites

### Server Requirements

- Linux server (Ubuntu 20.04+ or Debian 11+ recommended)
- Root or sudo access
- Public IP address or DDNS hostname
- Open UDP port 51820 (WireGuard)
- Open TCP port 8000 (API, optional)

### Software Requirements

```bash
# WireGuard
sudo apt update
sudo apt install wireguard wireguard-tools

# Python 3.9+
python3 --version  # Should be 3.9 or higher

# Python development headers
sudo apt install python3-dev python3-venv
```

## Step 1: WireGuard Server Setup

### 1.1 Generate Server Keys

```bash
# Create WireGuard directory
sudo mkdir -p /etc/wireguard
cd /etc/wireguard

# Generate server keypair
wg genkey | sudo tee privatekey | wg pubkey | sudo tee publickey

# Secure the private key
sudo chmod 600 privatekey
```

### 1.2 Create WireGuard Configuration

Create `/etc/wireguard/wg0.conf`:

```ini
[Interface]
# Server VPN IP
Address = 10.8.0.1/24

# Private key (replace with your generated key)
PrivateKey = <SERVER_PRIVATE_KEY_FROM_STEP_1.1>

# WireGuard port
ListenPort = 51820

# Enable IP forwarding
PostUp = sysctl -w net.ipv4.ip_forward=1
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT
PostUp = iptables -A FORWARD -o wg0 -j ACCEPT
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT
PostDown = iptables -D FORWARD -o wg0 -j ACCEPT

# Clients will be added automatically by the API
```

### 1.3 Enable IP Forwarding

```bash
# Enable permanently
echo "net.ipv4.ip_forward = 1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 1.4 Configure Firewall

```bash
# Allow WireGuard
sudo ufw allow 51820/udp

# Optional: Allow API access (configure carefully!)
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw enable
```

### 1.5 Start WireGuard

```bash
# Enable and start WireGuard
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# Check status
sudo wg show
```

## Step 2: Install the Gateway Application

### 2.1 Clone Repository

```bash
cd /opt
sudo git clone https://github.com/yourusername/udp-gateway.git
cd udp-gateway
```

### 2.2 Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2.3 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.4 Configure the Application

Edit `config/vpn_config.yaml`:

```yaml
vpn:
  interface: "wg0"
  server_port: 51820
  server_address: "10.8.0.1/24"
  public_endpoint: "your-server-ip.example.com"  # Your public IP or DDNS hostname

  # WireGuard config path
  config_path: "/etc/wireguard/wg0.conf"

api:
  host: "0.0.0.0"
  port: 8000

  # JWT secret (CHANGE THIS!)
  jwt_secret: "CHANGE-THIS-TO-A-RANDOM-STRING"
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 30

database:
  # SQLite for development
  url: "sqlite+aiosqlite:///./vpn_gateway.db"

  # PostgreSQL for production (recommended)
  # url: "postgresql+asyncpg://user:password@localhost/vpn_gateway"

radios:
  - name: "IO7T Radio"
    ip: "io7t.ddns.net"
    port: 1024
    enabled: true

logging:
  level: "INFO"
  file: "logs/vpn_gateway.log"
```

### 2.5 Initialize Database

```bash
# The database will be created automatically on first run
# Or use alembic for migrations:
alembic upgrade head
```

## Step 3: Start the API Server

### 3.1 Run Manually (for testing)

```bash
source venv/bin/activate
python -m src.api.main
```

The API will be available at `http://your-server:8000`

### 3.2 Run as Systemd Service (recommended for production)

Create `/etc/systemd/system/hpsdr-vpn-api.service`:

```ini
[Unit]
Description=HPSDR VPN Gateway API
After=network.target wg-quick@wg0.service
Requires=wg-quick@wg0.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/udp-gateway
Environment="PATH=/opt/udp-gateway/venv/bin"
ExecStart=/opt/udp-gateway/venv/bin/python -m src.api.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hpsdr-vpn-api
sudo systemctl start hpsdr-vpn-api
sudo systemctl status hpsdr-vpn-api
```

## Step 4: Create Admin User

Use the API to create the first admin user:

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "your-secure-password"
  }'
```

Then manually promote to admin in the database:

```bash
# SQLite
sqlite3 vpn_gateway.db "UPDATE users SET is_admin = 1 WHERE username = 'admin';"

# PostgreSQL
psql vpn_gateway -c "UPDATE users SET is_admin = true WHERE username = 'admin';"
```

## Step 5: Client Setup

### 5.1 User Registration

Users can register via API:

```bash
curl -X POST "http://your-server:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "email": "john@example.com",
    "password": "secure-password"
  }'
```

### 5.2 Login and Get VPN Config

```bash
# Login
TOKEN=$(curl -X POST "http://your-server:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "secure-password"}' \
  | jq -r '.access_token')

# Get VPN configuration
curl -X GET "http://your-server:8000/users/me/vpn-config" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.config' > john-vpn.conf
```

### 5.3 Install WireGuard Client

**Linux:**
```bash
sudo apt install wireguard

# Import configuration
sudo cp john-vpn.conf /etc/wireguard/wg0.conf
sudo wg-quick up wg0
```

**macOS:**
```bash
brew install wireguard-tools

# Or use WireGuard GUI app from App Store
# Import the .conf file
```

**Windows:**
```
1. Download WireGuard from https://www.wireguard.com/install/
2. Install
3. Import tunnel from file (john-vpn.conf)
4. Activate tunnel
```

**iOS/Android:**
```
1. Install WireGuard app from App Store/Play Store
2. Scan QR code (future feature) or import .conf file
3. Activate tunnel
```

## Step 6: Configure SDR Client

Once connected to VPN:

1. **Find radio on VPN**: The radio should be accessible at `10.8.0.X` (check admin panel for radio's VPN IP)
2. **Configure SDR software** (piHPSDR, Thetis, etc.):
   - Discovery: Broadcast on VPN subnet (10.8.0.0/24)
   - Radio IP: Use radio's VPN IP address
   - Port: 1024 (standard HPSDR)

## API Reference

### Authentication Endpoints

```
POST /auth/register          - Register new user
POST /auth/login             - Login and get JWT tokens
```

### User Endpoints

```
GET  /users/me               - Get current user info
GET  /users/me/vpn-config    - Get VPN configuration
```

### Admin Endpoints

```
GET    /admin/users          - List all users
PATCH  /admin/users/{id}     - Update user
DELETE /admin/users/{id}     - Delete user
GET    /admin/vpn/peers      - List connected VPN peers
```

### Monitoring

```
GET /health                  - Health check
GET /stats/system            - System statistics
```

### Example: List Users (Admin)

```bash
curl -X GET "http://your-server:8000/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Example: Disable User VPN Access

```bash
curl -X PATCH "http://your-server:8000/admin/users/5" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vpn_enabled": false}'
```

## Troubleshooting

### WireGuard not starting

```bash
# Check configuration
sudo wg show

# Check journal
sudo journalctl -u wg-quick@wg0 -n 50

# Test connectivity
sudo wg show wg0
```

### API not accessible

```bash
# Check if running
sudo systemctl status hpsdr-vpn-api

# Check logs
sudo journalctl -u hpsdr-vpn-api -n 100

# Check port
sudo netstat -tulpn | grep 8000
```

### Client can't connect to VPN

1. Check firewall allows UDP 51820
2. Verify server public endpoint is correct
3. Check WireGuard is running: `sudo wg show`
4. Verify client configuration has correct server public key

### Client connected but can't reach radio

1. Verify IP forwarding: `cat /proc/sys/net/ipv4/ip_forward` (should be 1)
2. Check routing on VPN: `ip route show`
3. Verify radio is accessible from server
4. Check VPN subnet in SDR client discovery settings

## Security Considerations

1. **Change JWT Secret**: Use a strong random string in production
2. **HTTPS**: Use reverse proxy (nginx) with SSL for API
3. **Firewall**: Restrict API access, only allow from trusted networks
4. **Strong Passwords**: Enforce password policies
5. **Regular Updates**: Keep WireGuard and system updated
6. **Audit Logs**: Monitor the audit_logs table regularly
7. **Backup Database**: Regular backups of user database

## Monitoring

### Check Active VPN Sessions

```bash
sudo wg show wg0
```

### View API Logs

```bash
sudo journalctl -u hpsdr-vpn-api -f
```

### Database Queries

```sql
-- Active users
SELECT username, email, vpn_ip_address, last_login FROM users WHERE is_active = 1;

-- Recent activity
SELECT username, action, timestamp, success FROM audit_logs ORDER BY timestamp DESC LIMIT 20;

-- Connection statistics
SELECT username, connection_count, last_vpn_connection FROM users ORDER BY connection_count DESC;
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/udp-gateway/issues
- Documentation: https://github.com/yourusername/udp-gateway/wiki
