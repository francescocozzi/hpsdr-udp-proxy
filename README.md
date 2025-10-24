# HPSDR VPN Gateway with Authentication

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![WireGuard](https://img.shields.io/badge/VPN-WireGuard-88171a.svg)](https://www.wireguard.com/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/version-2.1.0-blue)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)](https://github.com/francescocozzi/hpsdr-udp-proxy)

A complete VPN-based solution for secure, authenticated remote access to HPSDR radios (Hermes Lite 2) using WireGuard.

## Overview

This project provides a production-ready VPN gateway that enables multiple users to securely access remote HPSDR software-defined radios. Instead of using an application-level proxy (which has protocol compatibility issues), this solution uses **WireGuard VPN** to create secure tunnels, preserving full HPSDR protocol compatibility.

## Architecture

```
[SDR Client] <--WireGuard VPN--> [VPN Gateway Server] <---> [Hermes-Lite 2 Radio]
                                         |
                                  [Auth & User Mgmt]
                                  [REST API]
                                  [Config System]
```

## Key Features

### ✅ Production-Ready
- **WireGuard VPN**: Modern, fast, secure VPN technology
- **User Authentication**: JWT-based authentication system
- **Configuration Management**: Centralized config system (INI files + environment variables)
- **REST API**: Complete API for user and VPN management
- **Database Backend**: SQLite (development) or PostgreSQL (production)
- **Audit Logging**: Security and usage tracking
- **Systemd Integration**: Automatic service startup
- **Admin Panel**: Web-based user management (planned)

### ✅ Full Protocol Compatibility
- No packet modification or proxying
- Direct protocol compatibility with all HPSDR clients
- Low latency (<5ms VPN overhead)
- High throughput (supports full IQ streaming)

### ✅ Multi-User Support
- Unlimited users (hardware-limited)
- Individual VPN credentials per user
- Admin-controlled access enable/disable
- Connection tracking and statistics
- Automatic IP assignment

### ✅ Easy Configuration
- Single `config.ini` file for all settings
- Environment variable overrides
- Automatic WireGuard peer management
- No hardcoded values

## Components

### 1. Configuration System (`src/config.py`)
- Centralized configuration management
- INI file support with environment variable overrides
- Configurable VPN endpoint, API settings, database, security, logging
- **New in v2.1.0**

### 2. VPN Module (`src/vpn/`)
- **WireGuard Manager**: Automated peer configuration
- **User Database**: SQLAlchemy models for users, sessions, audit logs
- **Authentication**: JWT tokens, bcrypt password hashing

### 3. REST API (`src/api/`)
- User registration and login
- VPN configuration distribution
- Admin user management
- Statistics and monitoring

### 4. Legacy UDP Proxy (`main.py`)
- *Note: The UDP proxy approach had protocol compatibility issues*
- *Preserved for reference but not recommended for production*
- *See `docs/UDP_PROXY_ANALYSIS.md` for technical details*

## Quick Start

### Server Setup

See [docs/VPN_SETUP.md](docs/VPN_SETUP.md) for complete installation guide.

```bash
# 1. Install WireGuard
sudo apt install wireguard

# 2. Clone and setup
git clone https://github.com/francescocozzi/hpsdr-udp-proxy.git
cd hpsdr-udp-proxy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Create configuration file
cp config.example.ini config.ini
nano config.ini  # Edit with your settings

# 4. Configure WireGuard (see docs/VPN_SETUP.md)

# 5. Start API server
python -m src.api.main
```

### Configuration

Edit `config.ini`:

```ini
[vpn]
public_endpoint = your-server-ip-or-hostname
server_port = 51820
server_address = 10.8.0.1/24
interface = wg0

[api]
host = 0.0.0.0
port = 8000
jwt_secret = CHANGE-THIS-IN-PRODUCTION
jwt_algorithm = HS256
access_token_expire_minutes = 30

[database]
url = sqlite+aiosqlite:///./vpn_gateway.db
# For production PostgreSQL:
# url = postgresql+asyncpg://user:password@localhost/vpn_gateway

[security]
password_min_length = 8
require_email_verification = false
max_login_attempts = 5
lockout_duration_minutes = 15

[logging]
level = INFO
file = vpn_gateway.log
```

You can override any setting with environment variables:

```bash
export VPN_VPN_PUBLIC_ENDPOINT=192.168.1.229
export VPN_API_PORT=9000
export VPN_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/vpn
```

### Systemd Service (Recommended)

```bash
sudo nano /etc/systemd/system/vpn-gateway.service
```

```ini
[Unit]
Description=HPSDR VPN Gateway API Server
After=network.target wg-quick@wg0.service
Wants=wg-quick@wg0.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/hpsdr-udp-proxy
Environment="PATH=/path/to/hpsdr-udp-proxy/venv/bin"
ExecStart=/path/to/hpsdr-udp-proxy/venv/bin/python3 -m src.api.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn-gateway
sudo systemctl start vpn-gateway
sudo systemctl status vpn-gateway
```

### Client Registration

```bash
# Register user
curl -X POST "http://your-server:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "email": "john@example.com", "password": "SecurePass123"}'

# Login and get VPN config
TOKEN=$(curl -s -X POST "http://your-server:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "SecurePass123"}' \
  | jq -r '.access_token')

curl -X GET "http://your-server:8000/users/me/vpn-config" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.config' > my-vpn.conf
```

### Connect to VPN

```bash
# Import configuration
sudo cp my-vpn.conf /etc/wireguard/wg0-client.conf

# Connect
sudo wg-quick up wg0-client

# Check connection
sudo wg show
ping 10.8.0.1
```

### Use SDR Software

Once connected to VPN, configure your SDR software (piHPSDR, Thetis, PowerSDR, etc.) to discover radios on the VPN subnet (10.8.0.0/24).

## API Endpoints

### Authentication
```
POST /auth/register        - Register new user
POST /auth/login           - Login (returns JWT)
```

### User Management
```
GET  /users/me             - Get current user info
GET  /users/me/vpn-config  - Get WireGuard configuration
```

### Admin
```
GET    /admin/users        - List all users
PATCH  /admin/users/{id}   - Update user (enable/disable VPN)
DELETE /admin/users/{id}   - Delete user
GET    /admin/vpn/peers    - List connected peers
```

### Monitoring
```
GET /health               - Health check
GET /stats/system         - System statistics
```

Interactive API documentation available at `http://your-server:8000/docs`

## Documentation

- **[Configuration Guide](docs/CONFIG_DEPLOYMENT_GUIDE.md)** - Configuration system setup
- **[VPN Setup Guide](docs/VPN_SETUP.md)** - Complete server and client setup
- **[Architecture Overview](docs/ARCHITECTURE.md)** - Technical architecture
- **[API Reference](docs/API.md)** - Full API documentation
- **[UDP Proxy Analysis](docs/UDP_PROXY_ANALYSIS.md)** - Why we switched to VPN
- **[Changelog](CHANGELOG.md)** - Version history and changes

## Project Structure

```
hpsdr-udp-proxy/
├── src/
│   ├── config.py          # Configuration management (NEW v2.1.0)
│   ├── vpn/               # VPN management
│   │   ├── models.py      # Database models
│   │   ├── auth.py        # JWT authentication
│   │   └── wireguard_manager.py  # WireGuard automation
│   ├── api/               # REST API
│   │   └── main.py        # FastAPI application
│   ├── core/              # Legacy UDP proxy (reference only)
│   └── utils/             # Utilities
├── config/                # Configuration files
├── docs/                  # Documentation
│   ├── VPN_SETUP.md       # Setup guide
│   ├── CONFIG_DEPLOYMENT_GUIDE.md  # Config system guide
│   └── ...
├── config.example.ini     # Configuration template (NEW v2.1.0)
├── test_config.sh         # Config test script (NEW v2.1.0)
├── requirements.txt       # Python dependencies
├── CHANGELOG.md           # Version history
└── README.md              # This file
```

## Requirements

### Server
- Linux (Ubuntu 20.04+ or Debian 11+)
- Python 3.9+
- WireGuard
- Public IP or DDNS hostname

### Clients
- WireGuard client (Linux, macOS, Windows, iOS, Android)
- HPSDR-compatible SDR software (piHPSDR, Thetis, PowerSDR, etc.)

## Security

- ✅ WireGuard modern cryptography (ChaCha20, Poly1305)
- ✅ JWT-based API authentication
- ✅ Bcrypt password hashing
- ✅ Audit logging
- ✅ Per-user VPN keys
- ✅ Admin-controlled access
- ✅ Configurable security policies

**Production Checklist:**
- [ ] Change JWT secret key in `config.ini`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS for API (nginx reverse proxy)
- [ ] Configure firewall rules (UFW/iptables)
- [ ] Set up automated backups
- [ ] Monitor audit logs
- [ ] Configure systemd service for auto-start
- [ ] Set up monitoring and alerting

## Performance

- **VPN Overhead**: <5ms latency
- **Throughput**: Full bandwidth (WireGuard is very efficient)
- **Concurrent Users**: Hardware-limited (tested with 10+ users)
- **Protocol Compatibility**: 100% (no packet modification)

## Why VPN Instead of UDP Proxy?

After extensive debugging, we discovered that the HPSDR protocol (specifically Hermes-Lite 2) has requirements that make application-level UDP proxying problematic:

1. **UDP Source Address Dependency**: Clients derive radio location from UDP source addresses
2. **State Machine Timing**: Protocol has timing requirements that proxying affects
3. **Connection Verification**: Clients perform connectivity checks that fail through proxies

**VPN Solution Benefits:**
- ✅ Zero protocol modification
- ✅ Works with all HPSDR clients
- ✅ Better security (encrypted tunnel)
- ✅ Simpler architecture
- ✅ Better performance

See [docs/UDP_PROXY_ANALYSIS.md](docs/UDP_PROXY_ANALYSIS.md) for technical details.

## Development Status

**Current Version**: 2.1.0 (2025-10-24)

**Recent Updates:**
- ✅ Configuration management system
- ✅ Systemd service integration
- ✅ Environment variable overrides
- ✅ Improved documentation

**Completed Features:**
- ✅ VPN management system
- ✅ User authentication
- ✅ REST API
- ✅ WireGuard automation
- ✅ Database backend
- ✅ Comprehensive documentation

**Planned Features:**
- ⏸️ Web dashboard (v2.2.0)
- ⏸️ VPN config regeneration API (v2.2.0)
- ⏸️ Time slot management (v2.3.0)
- ⏸️ QR code generation for mobile (v2.2.0)
- ⏸️ Email verification (v2.3.0)

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Migration from UDP Proxy

If you were using the previous UDP proxy version (1.x), the VPN approach is a complete replacement with better compatibility. The old proxy code is preserved in `main.py` for reference but is not recommended for production use.

## Troubleshooting

### Config System Issues

```bash
# Test configuration loading
python3 -c "from src.config import config; print(config.vpn_public_endpoint)"

# Check config file syntax
cat config.ini | grep public_endpoint

# Test with environment variables
export VPN_VPN_PUBLIC_ENDPOINT=192.168.1.100
python3 -c "from src.config import config; print(config.vpn_public_endpoint)"
```

### Service Issues

```bash
# Check service status
sudo systemctl status vpn-gateway

# View logs
sudo journalctl -u vpn-gateway -f

# Restart service
sudo systemctl restart vpn-gateway
```

### WireGuard Issues

```bash
# Check peers
sudo wg show wg0

# Check interface
ip addr show wg0

# Restart WireGuard
sudo wg-quick down wg0 && sudo wg-quick up wg0
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - See [LICENSE](LICENSE) file.

**Copyright (c) 2025 Francesco Cozzi**

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Acknowledgments

- HPSDR/OpenHPSDR community
- Hermes-Lite 2 project
- WireGuard project
- FastAPI framework
- SQLAlchemy project

## Support

- **Issues**: [https://github.com/francescocozzi/hpsdr-udp-proxy/issues](https://github.com/francescocozzi/hpsdr-udp-proxy/issues)
- **Wiki**: [https://github.com/francescocozzi/hpsdr-udp-proxy/wiki](https://github.com/francescocozzi/hpsdr-udp-proxy/wiki)
- **Discussions**: [https://github.com/francescocozzi/hpsdr-udp-proxy/discussions](https://github.com/francescocozzi/hpsdr-udp-proxy/discussions)

## Related Projects

- [OpenHPSDR](https://openhpsdr.org/) - Open Source High Performance Software Defined Radio
- [Hermes-Lite 2](http://hermeslite.com/) - Low-cost HPSDR transceiver
- [WireGuard](https://www.wireguard.com/) - Fast, modern, secure VPN tunnel
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [piHPSDR](https://github.com/g0orx/pihpsdr) - HPSDR client for Raspberry Pi and Linux

## Star History

If you find this project useful, please consider giving it a star on GitHub!

[![Star History](https://img.shields.io/github/stars/francescocozzi/hpsdr-udp-proxy?style=social)](https://github.com/francescocozzi/hpsdr-udp-proxy/stargazers)
