-- HPSDR Proxy Database Schema
-- PostgreSQL / SQLite compatible

-- Enable UUID extension (PostgreSQL only)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    full_name VARCHAR(100),
    enabled BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Radios table
CREATE TABLE IF NOT EXISTS radios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    port INTEGER DEFAULT 1024,
    mac_address VARCHAR(17),
    description TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    radio_id INTEGER REFERENCES radios(id) ON DELETE SET NULL,
    token VARCHAR(512) UNIQUE NOT NULL,
    refresh_token VARCHAR(512) UNIQUE,
    client_ip VARCHAR(45) NOT NULL,
    client_port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    user_agent TEXT,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Time slots reservations table
CREATE TABLE IF NOT EXISTS time_slots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    radio_id INTEGER NOT NULL REFERENCES radios(id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'reserved' CHECK (status IN ('reserved', 'active', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_slot FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_radio_slot FOREIGN KEY (radio_id) REFERENCES radios(id),
    CONSTRAINT valid_time_range CHECK (end_time > start_time)
);

-- Activity log table
CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Statistics table for monitoring
CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL PRIMARY KEY,
    radio_id INTEGER REFERENCES radios(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    packets_received BIGINT DEFAULT 0,
    packets_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    bytes_sent BIGINT DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    average_latency_ms FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    interval_seconds INTEGER DEFAULT 60
);

-- API keys table (for programmatic access)
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    enabled BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    CONSTRAINT fk_user_apikey FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_enabled ON users(enabled);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(active, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_ip, client_port);

CREATE INDEX IF NOT EXISTS idx_time_slots_user ON time_slots(user_id);
CREATE INDEX IF NOT EXISTS idx_time_slots_radio ON time_slots(radio_id);
CREATE INDEX IF NOT EXISTS idx_time_slots_time ON time_slots(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_time_slots_status ON time_slots(status);

CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_log_action ON activity_log(action);

CREATE INDEX IF NOT EXISTS idx_statistics_radio ON statistics(radio_id);
CREATE INDEX IF NOT EXISTS idx_statistics_session ON statistics(session_id);
CREATE INDEX IF NOT EXISTS idx_statistics_timestamp ON statistics(timestamp);

CREATE INDEX IF NOT EXISTS idx_radios_enabled ON radios(enabled);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

-- Create default admin user (password: admin123 - CHANGE IN PRODUCTION!)
-- Password hash is bcrypt hash of "admin123"
INSERT INTO users (username, password_hash, email, full_name, enabled, is_admin)
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqYhZqKqfi', 'admin@example.com', 'Administrator', TRUE, TRUE)
ON CONFLICT (username) DO NOTHING;

-- Create sample radio (adjust IP and MAC for your setup)
INSERT INTO radios (name, ip_address, port, mac_address, description, enabled)
VALUES ('Hermes Lite 2 - Radio 1', '192.168.1.100', 1024, '00:1C:C0:A2:12:34', 'Main SDR radio', TRUE)
ON CONFLICT DO NOTHING;

-- Views for easier querying

-- Active sessions view
CREATE OR REPLACE VIEW active_sessions AS
SELECT
    s.id,
    s.token,
    u.username,
    u.email,
    r.name as radio_name,
    r.ip_address as radio_ip,
    s.client_ip,
    s.client_port,
    s.created_at,
    s.expires_at,
    s.last_activity,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - s.last_activity)) as idle_seconds
FROM sessions s
JOIN users u ON s.user_id = u.id
LEFT JOIN radios r ON s.radio_id = r.id
WHERE s.active = TRUE
AND s.expires_at > CURRENT_TIMESTAMP;

-- Current and upcoming reservations
CREATE OR REPLACE VIEW current_reservations AS
SELECT
    ts.id,
    u.username,
    r.name as radio_name,
    ts.start_time,
    ts.end_time,
    ts.status,
    EXTRACT(EPOCH FROM (ts.end_time - ts.start_time)) / 60 as duration_minutes
FROM time_slots ts
JOIN users u ON ts.user_id = u.id
JOIN radios r ON ts.radio_id = r.id
WHERE ts.status IN ('reserved', 'active')
AND ts.end_time > CURRENT_TIMESTAMP
ORDER BY ts.start_time;

-- Radio usage statistics
CREATE OR REPLACE VIEW radio_statistics AS
SELECT
    r.id,
    r.name,
    COUNT(DISTINCT s.id) as total_sessions,
    SUM(st.packets_received) as total_packets_received,
    SUM(st.packets_sent) as total_packets_sent,
    AVG(st.average_latency_ms) as avg_latency_ms,
    MAX(s.last_activity) as last_used
FROM radios r
LEFT JOIN sessions s ON r.id = s.radio_id
LEFT JOIN statistics st ON r.id = st.radio_id
GROUP BY r.id, r.name;

-- User activity summary
CREATE OR REPLACE VIEW user_activity AS
SELECT
    u.id,
    u.username,
    u.email,
    COUNT(DISTINCT s.id) as total_sessions,
    COUNT(DISTINCT ts.id) as total_reservations,
    MAX(s.last_activity) as last_activity,
    u.last_login
FROM users u
LEFT JOIN sessions s ON u.id = s.user_id
LEFT JOIN time_slots ts ON u.id = ts.user_id
GROUP BY u.id, u.username, u.email, u.last_login;

-- Triggers for updated_at timestamps

-- PostgreSQL trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_radios_updated_at BEFORE UPDATE ON radios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_time_slots_updated_at BEFORE UPDATE ON time_slots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
