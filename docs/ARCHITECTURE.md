# HPSDR Proxy Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│            (deskHPSDR, PowerSDR, Spark SDR, etc.)              │
└──────────────────┬──────────────────────────────────────────────┘
                   │ UDP Packets (HPSDR Protocol)
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      HPSDR UDP PROXY                            │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  UDP Listener (Port 1024)                              │    │
│  │  - Receive packets from clients and radios             │    │
│  │  - AsyncIO-based for high performance                  │    │
│  └──────────────────┬─────────────────────────────────────┘    │
│                     │                                            │
│  ┌──────────────────▼─────────────────────────────────────┐    │
│  │  Packet Handler                                        │    │
│  │  - Parse HPSDR protocol (Protocol 1 & 2)              │    │
│  │  - Identify packet types (Discovery, Data, etc.)      │    │
│  │  - Extract metadata                                    │    │
│  └──────────────────┬─────────────────────────────────────┘    │
│                     │                                            │
│  ┌──────────────────▼─────────────────────────────────────┐    │
│  │  Authentication Manager                                │    │
│  │  - Verify JWT tokens                                   │    │
│  │  - Check user permissions                              │    │
│  │  - Validate time slots                                 │    │
│  └──────────────────┬─────────────────────────────────────┘    │
│                     │                                            │
│  ┌──────────────────▼─────────────────────────────────────┐    │
│  │  Session Manager                                       │    │
│  │  - Track active client sessions                       │    │
│  │  - Map client ↔ radio connections                     │    │
│  │  - Handle timeouts and cleanup                        │    │
│  └──────────────────┬─────────────────────────────────────┘    │
│                     │                                            │
│  ┌──────────────────▼─────────────────────────────────────┐    │
│  │  Packet Forwarder                                      │    │
│  │  - Forward packets to appropriate destination         │    │
│  │  - Transparent bidirectional forwarding               │    │
│  │  - Low-latency operation                              │    │
│  └──────────────────┬─────────────────────────────────────┘    │
│                     │                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  REST API (Port 8080)                                    │  │
│  │  - User management                                       │  │
│  │  - Authentication endpoints                              │  │
│  │  - Time slot reservations                                │  │
│  │  - Statistics and monitoring                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Database (PostgreSQL/SQLite)                            │  │
│  │  - Users, sessions, radios                               │  │
│  │  - Time slots, activity logs                             │  │
│  │  - Statistics                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                     │ UDP Packets (Authenticated)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SDR Radios (Hermes Lite 2, etc.)            │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. UDP Listener

**Purpose**: High-performance UDP packet reception and transmission

**Key Features**:
- AsyncIO-based for non-blocking I/O
- Handles 1000+ packets/second
- Support for multiple listening ports
- Socket optimization (large buffers, broadcast support)

**Files**:
- `src/core/udp_listener.py`

### 2. Packet Handler

**Purpose**: Parse and analyze HPSDR protocol packets

**Supported Protocols**:
- HPSDR Protocol 1 (Metis/Hermes)
- HPSDR Protocol 2 (Hermes Lite 2)

**Packet Types**:
- Discovery (0xEFFE02)
- Data packets (I/Q samples)
- Control commands
- Programming packets

**Files**:
- `src/core/packet_handler.py`

### 3. Authentication Manager

**Purpose**: Secure authentication and authorization

**Features**:
- JWT token-based authentication
- Password hashing (bcrypt)
- Failed login attempt tracking
- Account lockout mechanism
- API key support

**Authentication Flow**:
```
1. Client sends credentials → POST /api/auth/login
2. Verify username/password
3. Generate JWT token
4. Return token to client
5. Client includes token in subsequent requests
```

**Files**:
- `src/auth/auth_manager.py`
- `src/auth/models.py`

### 4. Session Manager

**Purpose**: Track and manage active client sessions

**Session Lifecycle**:
```
1. Discovery packet received
2. Extract/validate authentication token
3. Create session record
4. Map client address → radio
5. Monitor activity (heartbeat)
6. Cleanup on timeout/disconnect
```

**Session State**:
- Client IP:Port
- Radio assignment
- User ID
- Token
- Last activity timestamp
- Expiration time

**Files**:
- `src/core/session_manager.py`

### 5. Packet Forwarder

**Purpose**: Transparent bidirectional packet forwarding

**Features**:
- Zero-copy forwarding (when possible)
- Low latency (<5ms added)
- Handles NAT traversal
- Automatic address translation

**Forwarding Rules**:
```
Client → Proxy: Check auth, forward to radio
Radio → Proxy: Lookup session, forward to client
```

**Files**:
- `src/core/forwarder.py`

### 6. REST API

**Purpose**: Management interface and authentication endpoint

**Technology**: FastAPI (async, high-performance)

**Endpoints**:
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh token
- `GET /api/users` - List users (admin)
- `POST /api/users` - Create user (admin)
- `GET /api/radios` - List radios
- `POST /api/timeslots` - Reserve time slot
- `GET /api/statistics` - Get statistics

**Files**:
- `src/api/rest_api.py`
- `src/api/routes.py`

### 7. Database

**Purpose**: Persistent data storage

**Supported Databases**:
- PostgreSQL (recommended for production)
- SQLite (development/testing)

**Schema**:
- `users` - User accounts
- `radios` - Radio configurations
- `sessions` - Active sessions
- `time_slots` - Reservations
- `activity_log` - Audit trail
- `statistics` - Performance metrics

**Files**:
- `src/auth/models.py` (SQLAlchemy models)
- `src/auth/db_manager.py` (Database interface)
- `database/schema.sql` (SQL schema)

## Data Flow

### Discovery Flow

```
1. Client broadcasts discovery packet
   └─> 0xEFFE02 + padding

2. Proxy receives packet
   ├─> Parse packet (PacketHandler)
   ├─> Check authentication (AuthManager)
   │   ├─> Extract token from packet/session
   │   └─> Validate token
   ├─> Check/create session (SessionManager)
   └─> Forward to radio (PacketForwarder)

3. Radio responds with discovery
   └─> 0xEFFE02 + MAC + Board ID + ...

4. Proxy receives radio response
   ├─> Lookup session by radio address
   ├─> Translate addresses
   └─> Forward to client

5. Client receives discovery response
   └─> Establishes connection
```

### Data Stream Flow

```
1. Client sends I/Q data packet
   └─> 0xEFFE01 + seq + control + IQ data

2. Proxy receives packet
   ├─> Validate session (fast path)
   │   ├─> Check client address in session cache
   │   └─> Verify not expired
   ├─> Update last activity timestamp
   └─> Forward to assigned radio

3. Radio processes and responds
   └─> Audio/IQ data packets

4. Proxy receives radio response
   ├─> Lookup client from session
   └─> Forward to client

5. Client receives and processes data
```

## Performance Considerations

### Latency Optimization

- **AsyncIO**: Non-blocking I/O for maximum throughput
- **Zero-copy forwarding**: Minimal memory operations
- **Session caching**: Fast session lookup (O(1))
- **Direct forwarding**: No unnecessary processing in data path

### Scalability

- **Concurrent connections**: Limited by system resources
- **Packet rate**: 1000+ packets/second per radio
- **Multiple radios**: Supported via session mapping

### Resource Usage

**Memory**:
- Base: ~50MB
- Per session: ~10KB
- Packet buffers: Configurable

**CPU**:
- Idle: <1%
- Active (1 radio): 5-10%
- Active (multiple radios): Scales linearly

**Network**:
- Bandwidth: ~8-10 Mbps per active radio
- Latency overhead: <5ms typically

## Security Architecture

### Authentication Layers

1. **REST API**: JWT token + password
2. **UDP Packets**: Session validation
3. **Database**: Hashed passwords (bcrypt)

### Attack Mitigation

- **Rate limiting**: Prevent brute force
- **Account lockout**: After failed attempts
- **Token expiration**: Time-limited access
- **IP whitelist/blacklist**: Network filtering
- **Activity logging**: Audit trail

## Extension Points

### Adding New Features

1. **Custom packet processing**: Extend `PacketHandler`
2. **Authentication methods**: Extend `AuthManager`
3. **API endpoints**: Add routes to `routes.py`
4. **Database models**: Add to `models.py`

### Integration Options

- **MQTT**: Publish statistics/events
- **Grafana**: Visualization dashboard
- **Prometheus**: Metrics export
- **Webhook**: Event notifications

## Configuration

All components are configured via `config/config.yaml`:

```yaml
proxy:      # UDP listener config
database:   # Database connection
radios:     # Radio definitions
auth:       # Authentication settings
api:        # REST API settings
logging:    # Logging configuration
performance: # Performance tuning
security:   # Security policies
timeslots:  # Reservation rules
```

## Monitoring and Observability

### Logging

- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Outputs**: File (rotating), Console
- **Format**: Text or JSON

### Metrics

- Packet counts (received/sent)
- Byte counts
- Error rates
- Session counts
- Latency measurements

### Health Checks

- Database connectivity
- Radio reachability
- Session validity
- Resource usage

## Deployment Topologies

### Single Host

```
[Client] ←→ [Proxy + DB] ←→ [Radio]
```

### Distributed

```
[Clients] ←→ [Proxy] ←→ [Radios]
              ↓
         [DB Server]
```

### High Availability

```
[Clients] ←→ [Load Balancer]
              ├─> [Proxy 1] ←→ [Radio 1]
              └─> [Proxy 2] ←→ [Radio 2]
                   ↓
              [DB Cluster]
```

## Future Enhancements

- [ ] WebSocket API for real-time updates
- [ ] Web-based dashboard
- [ ] Multi-tenancy support
- [ ] Advanced scheduling (recurring slots)
- [ ] QoS and bandwidth management
- [ ] Encrypted UDP transport
- [ ] Plugin system for extensibility
