# Quick Start Guide

Get your HPSDR Proxy up and running in 5 minutes!

## Prerequisites

- Python 3.11+
- Basic network configuration knowledge

## Installation Steps

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install packages
pip install -r requirements.txt
```

### 2. Configure

```bash
# Copy example config
cp config/config.yaml.example config/config.yaml

# Edit with your settings
nano config/config.yaml
```

**Minimum required changes:**

```yaml
radios:
  - name: "My Radio"
    ip: "192.168.1.100"      # ← Your radio's IP
    port: 1024
    mac: "00:1C:C0:A2:12:34" # ← Your radio's MAC
    enabled: true

auth:
  jwt_secret: "CHANGE-ME-TO-RANDOM-SECRET"  # ← Generate random secret
```

### 3. Initialize Database

```bash
python scripts/init_db.py
```

### 4. Run!

```bash
python main.py
```

You should see:

```
============================================================
HPSDR UDP Proxy/Gateway Starting...
============================================================
INFO - Packet handler initialized
INFO - UDP listener started on 0.0.0.0:1024
INFO - All components initialized successfully!
INFO - Proxy is now running. Press Ctrl+C to stop.
```

## Test Connection

### From deskHPSDR

1. Open deskHPSDR
2. Go to Setup → Discovery
3. Set server IP to your proxy IP
4. Click Discover

You should see your radio appear!

## Default Credentials

**Admin account** (created automatically):
- Username: `admin`
- Password: `admin123`

**⚠️ IMPORTANT: Change this password immediately!**

## Next Steps

- [ ] Change admin password
- [ ] Create user accounts
- [ ] Configure time slots (optional)
- [ ] Set up monitoring (optional)
- [ ] Read full documentation

## Common Issues

### "Port 1024 already in use"

```bash
# Check what's using it
sudo lsof -i :1024

# Option 1: Stop the other service
# Option 2: Change port in config.yaml
```

### "Permission denied" on port 1024

Ports < 1024 need privileges:

```bash
# Linux: Allow Python to bind privileged ports
sudo setcap CAP_NET_BIND_SERVICE=+eip $(which python3)

# Or run as root (not recommended)
sudo python main.py

# Or use a higher port (e.g., 11024) in config
```

### "Database connection failed"

For SQLite (default):
```bash
# Create database directory
mkdir -p database
chmod 755 database
```

For PostgreSQL:
```bash
# Ensure PostgreSQL is running
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### Can't connect from deskHPSDR

1. Check firewall:
```bash
# Allow UDP 1024
sudo ufw allow 1024/udp
```

2. Check proxy is listening:
```bash
sudo netstat -tulpn | grep 1024
```

3. Check logs:
```bash
tail -f logs/proxy.log
```

## Help & Support

- **Full docs**: See `docs/INSTALLATION.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Issues**: Open a GitHub issue

## Testing

```bash
# Run with verbose logging
python main.py -v

# Monitor logs in real-time
tail -f logs/proxy.log

# Test discovery packet
echo -ne '\xef\xfe\x02' | nc -u localhost 1024
```

## Security Checklist

Before going to production:

- [ ] Change admin password
- [ ] Generate secure JWT secret
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS for API
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Review security settings in config

## Configuration Reference

### Minimal Config (SQLite)

```yaml
proxy:
  listen_address: "0.0.0.0"
  listen_port: 1024

database:
  type: "sqlite"
  sqlite_path: "database/proxy.db"

radios:
  - name: "My Radio"
    ip: "192.168.1.100"
    port: 1024
    enabled: true

auth:
  jwt_secret: "your-secret-here"
```

### Production Config (PostgreSQL)

```yaml
proxy:
  listen_address: "0.0.0.0"
  listen_port: 1024
  max_sessions: 50

database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  name: "hpsdr_proxy"
  user: "proxy_user"
  password: "secure_password"

radios:
  - name: "Radio 1"
    ip: "192.168.1.100"
    port: 1024
    mac: "00:1C:C0:A2:12:34"
    enabled: true

auth:
  jwt_secret: "generated-secure-secret"
  token_expiry: 3600
  max_login_attempts: 5

api:
  host: "0.0.0.0"
  port: 8080
  cors_enabled: true

logging:
  level: "INFO"
  file: "logs/proxy.log"

security:
  require_authentication: true
  ip_whitelist_enabled: false

timeslots:
  enabled: true
  max_duration: 240
```

## Performance Tips

- Use PostgreSQL for production
- Enable statistics: `performance.stats_enabled: true`
- Adjust worker threads: `performance.worker_threads: 4`
- Monitor resource usage
- Keep logs rotated

## Backup

Important files to backup:

```bash
# Configuration
config/config.yaml

# Database (SQLite)
database/proxy.db

# Logs (optional)
logs/*.log
```

For PostgreSQL:
```bash
pg_dump hpsdr_proxy > backup.sql
```

## Upgrading

```bash
# Pull latest code
git pull

# Update dependencies
pip install -r requirements.txt --upgrade

# Run migrations (if any)
python scripts/migrate_db.py

# Restart proxy
python main.py
```

---

**Need help?** Check the full documentation in the `docs/` directory!
