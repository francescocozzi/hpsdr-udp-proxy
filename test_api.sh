#!/bin/bash
# Test script for HPSDR VPN Gateway API

API_URL="http://localhost:8000"

echo "========================================="
echo "HPSDR VPN Gateway API Test Suite"
echo "========================================="
echo ""

# Test 1: Health Check
echo "1. Testing Health Check Endpoint..."
curl -s "$API_URL/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: User Registration
echo "2. Testing User Registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePassword123"
  }')
echo "$REGISTER_RESPONSE" | python3 -m json.tool
echo ""
echo ""

# Test 3: User Login
echo "3. Testing User Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePassword123"
  }')
echo "$LOGIN_RESPONSE" | python3 -m json.tool

# Extract access token
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
echo ""
echo "Access Token: $ACCESS_TOKEN"
echo ""
echo ""

if [ -z "$ACCESS_TOKEN" ]; then
  echo "ERROR: Failed to get access token. Stopping tests."
  exit 1
fi

# Test 4: Get Current User Info
echo "4. Testing Get Current User Info..."
curl -s "$API_URL/users/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
echo ""
echo ""

# Test 5: Get VPN Configuration
echo "5. Testing Get VPN Configuration..."
VPN_CONFIG=$(curl -s "$API_URL/users/me/vpn-config" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$VPN_CONFIG" | python3 -m json.tool
echo ""
echo ""

# Test 6: System Statistics (authenticated user)
echo "6. Testing System Statistics..."
curl -s "$API_URL/stats/system" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
echo ""
echo ""

echo "========================================="
echo "API Tests Completed!"
echo "========================================="
