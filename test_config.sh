#!/bin/bash
# Script to test the new configuration system

echo "========================================="
echo "HPSDR VPN Gateway - Configuration Test"
echo "========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "src/config.py" ]; then
    echo "❌ Error: Run this script from the project root directory"
    exit 1
fi

echo "Step 1: Checking if config.ini exists..."
if [ -f "config.ini" ]; then
    echo "✅ config.ini found"
else
    echo "⚠️  config.ini not found, creating from example..."
    if [ -f "config.example.ini" ]; then
        cp config.example.ini config.ini
        echo "✅ Created config.ini from config.example.ini"
        echo ""
        echo "IMPORTANT: Edit config.ini and set your public_endpoint!"
        echo "Run: nano config.ini"
        echo ""
    else
        echo "❌ Error: config.example.ini not found"
        exit 1
    fi
fi

echo ""
echo "Step 2: Displaying current VPN configuration..."
echo "------------------------------------------------"
if [ -f "config.ini" ]; then
    echo "[VPN Settings]"
    grep "public_endpoint" config.ini || echo "public_endpoint not set"
    grep "server_port" config.ini || echo "server_port not set"
    grep "server_address" config.ini || echo "server_address not set"
    grep "interface" config.ini || echo "interface not set"
fi

echo ""
echo "Step 3: Testing configuration module..."
echo "------------------------------------------------"
python3 -c "
from src.config import config

print(f'VPN Public Endpoint: {config.vpn_public_endpoint}')
print(f'VPN Server Port: {config.vpn_server_port}')
print(f'VPN Server Address: {config.vpn_server_address}')
print(f'VPN Interface: {config.vpn_interface}')
print(f'API Host: {config.api_host}')
print(f'API Port: {config.api_port}')
print(f'Database URL: {config.database_url}')
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configuration module loaded successfully"
else
    echo ""
    echo "❌ Error loading configuration module"
    exit 1
fi

echo ""
echo "Step 4: Testing API server startup (will start for 3 seconds)..."
echo "------------------------------------------------"
timeout 3 python3 -m src.api.main > /tmp/api_test.log 2>&1 &
API_PID=$!
sleep 2

if ps -p $API_PID > /dev/null 2>&1; then
    echo "✅ API server started successfully"
    kill $API_PID 2>/dev/null

    echo ""
    echo "Checking startup log for configuration messages:"
    grep -i "wireguard manager initialized" /tmp/api_test.log || echo "⚠️  WireGuard init message not found"
else
    echo "❌ API server failed to start"
    echo ""
    echo "Error log:"
    cat /tmp/api_test.log
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Configuration Test Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit config.ini to set your actual public_endpoint"
echo "2. Test user registration with:"
echo "   curl -X POST http://localhost:8000/auth/register \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"username\": \"bob\", \"email\": \"bob@example.com\", \"password\": \"BobPassword123\"}'"
echo ""
echo "3. Retrieve VPN config and check endpoint is correct"
echo ""
