# Installation Guide

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 13+ (recommended) or SQLite 3.35+
- Network access to HPSDR-compatible radio(s)
- Linux/macOS/Windows (tested on Linux and macOS)

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone <repository-url>
cd udp-gateway

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/macOS
# OR
venv\Scripts\activate  # On Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Database Setup

#### Option A: PostgreSQL (Recommended for Production)

```bash
# Install PostgreSQL (if not already installed)
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS (with Homebrew):
brew install postgresql

# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE hpsdr_proxy;
CREATE USER proxy_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE hpsdr_proxy TO proxy_user;
\q
```

#### Option B: SQLite (For Development/Testing)

SQLite requires no additional setup. The database file will be created automatically.

### 3. Configuration

```bash
# Copy example configuration
cp config/config.yaml.example config/config.yaml

# Edit configuration
nano config/config.yaml  # or use your preferred editor
```

**Important settings to configure:**

```yaml
database:
  type: "postgresql"  # or "sqlite"
  host: "localhost"
  port: 5432
  name: "hpsdr_proxy"
  user: "proxy_user"
  password: "your_secure_password"

radios:
  - name: "Your Radio Name"
    ip: "192.168.1.100"  # Your radio's IP
    port: 1024
    mac: "00:1C:C0:A2:12:34"  # Your radio's MAC
    enabled: true

auth:
  jwt_secret: "CHANGE-THIS-TO-A-RANDOM-SECRET-KEY"
```

### 4. Initialize Database

```bash
# Create database tables
python scripts/init_db.py

# With custom config path:
python scripts/init_db.py -c /path/to/config.yaml
```

This will create all necessary tables and insert a default admin user:
- Username: `admin`
- Password: `admin123`

**⚠️ Change the admin password immediately after first login!**

### 5. Run the Proxy

```bash
# Start the proxy
python main.py

# With verbose logging:
python main.py -v

# With custom config:
python main.py -c /path/to/config.yaml
```

## Configuration Details

### Proxy Settings

```yaml
proxy:
  listen_address: "0.0.0.0"  # Listen on all interfaces
  listen_port: 1024          # HPSDR standard port
  buffer_size: 2048          # UDP buffer size
  session_timeout: 60        # Session timeout in seconds
  max_sessions: 50           # Maximum concurrent sessions
```

### Radio Configuration

Add each radio you want to proxy:

```yaml
radios:
  - name: "Hermes Lite 2 - Main"
    ip: "192.168.1.100"
    port: 1024
    mac: "00:1C:C0:A2:12:34"
    enabled: true
    description: "Main SDR radio"
```

### Authentication Settings

```yaml
auth:
  jwt_secret: "your-secret-key"  # Generate a random secret!
  token_expiry: 3600             # Token valid for 1 hour
  max_login_attempts: 5          # Lock after 5 failed attempts
  lockout_duration: 300          # Lockout for 5 minutes
```

**Generate a secure JWT secret:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Firewall Configuration

The proxy needs the following ports:

- **UDP 1024**: HPSDR protocol (configurable)
- **TCP 8080**: REST API (configurable)

### Linux (iptables)

```bash
sudo iptables -A INPUT -p udp --dport 1024 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

### Linux (firewalld)

```bash
sudo firewall-cmd --permanent --add-port=1024/udp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### macOS

```bash
# macOS firewall typically allows outgoing and allows incoming for apps
# No additional configuration usually needed for development
```

## Client Configuration

### deskHPSDR Setup

1. In deskHPSDR, go to Discovery settings
2. Set the IP address to your proxy server IP
3. The proxy will handle authentication transparently

### First Connection

On first connection, the client will need to authenticate. Use the REST API or web interface to:

1. Create a user account
2. Login to get an authentication token
3. Include token in subsequent connections

## Troubleshooting

### Database Connection Issues

**PostgreSQL connection refused:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql
```

**Permission denied:**
```sql
-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE hpsdr_proxy TO proxy_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO proxy_user;
```

### Port Already in Use

If port 1024 is already in use:

1. Edit `config/config.yaml` and change `listen_port`
2. Update firewall rules
3. Update client configuration

```bash
# Find what's using port 1024
sudo lsof -i :1024
# or
sudo netstat -tulpn | grep 1024
```

### Permission Denied on Port 1024

Ports below 1024 require root/admin privileges:

**Option 1: Run as root (not recommended)**
```bash
sudo python main.py
```

**Option 2: Allow Python to bind privileged ports (Linux)**
```bash
sudo setcap CAP_NET_BIND_SERVICE=+eip $(which python3)
```

**Option 3: Use a different port**
Edit config and use port > 1024 (e.g., 11024)

### Log File Permission Issues

```bash
# Create log directory with correct permissions
mkdir -p logs
chmod 755 logs
```

## Testing the Installation

### 1. Check if proxy is running

```bash
# Check if listening on correct port
sudo netstat -tulpn | grep 1024

# Or with ss:
sudo ss -tulpn | grep 1024
```

### 2. Test with discovery packet

```bash
# Send discovery packet (example with netcat)
echo -ne '\xef\xfe\x02' | nc -u -w1 <proxy-ip> 1024
```

### 3. Check logs

```bash
# Monitor logs
tail -f logs/proxy.log
```

## Next Steps

- [API Documentation](API.md) - REST API reference
- [Architecture](ARCHITECTURE.md) - System architecture details
- [Development](DEVELOPMENT.md) - Development guide

## Production Deployment

For production deployment, see:
- [Production Guide](PRODUCTION.md)
- [Security Best Practices](SECURITY.md)
- [Performance Tuning](PERFORMANCE.md)
