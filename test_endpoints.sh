#!/bin/bash
# Test completo de todos los endpoints del sistema TagFS

set -e

echo "=========================================="
echo "PRUEBA COMPLETA DE ENDPOINTS - TagFS"
echo "=========================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para test
test_endpoint() {
    local name="$1"
    local command="$2"
    local expected_status="$3"
    
    echo -n "Testing $name... "
    
    response=$(eval "$command" 2>&1)
    status=$?
    
    if [ $status -eq 0 ] && [[ "$response" != *"Internal Server Error"* ]] && [[ "$response" != *"404"* ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        echo "  Response: ${response:0:100}..."
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "  Response: $response"
        return 1
    fi
}

sleep 5

# 1. Test Health Check
echo -e "\n${YELLOW}=== 1. Health Check ===${NC}"
test_endpoint "GET /" \
    "curl -s http://localhost:8000/"

# 2. Test Register
echo -e "\n${YELLOW}=== 2. User Registration ===${NC}"
test_endpoint "POST /auth/register (alice)" \
    "curl -s -X POST http://localhost:8000/auth/register \
    -H 'Content-Type: application/json' \
    -d '{\"username\": \"alice\", \"email\": \"alice@test.com\", \"password\": \"alice123\"}'"

test_endpoint "POST /auth/register (bob)" \
    "curl -s -X POST http://localhost:8000/auth/register \
    -H 'Content-Type: application/json' \
    -d '{\"username\": \"bob\", \"email\": \"bob@test.com\", \"password\": \"bob123\"}'"

# 3. Test Login
echo -e "\n${YELLOW}=== 3. Authentication ===${NC}"
echo "Logging in as admin..."
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login-json \
    -H 'Content-Type: application/json' \
    -d '{"username": "admin", "password": "123456"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ADMIN_TOKEN" ]; then
    echo -e "${RED}✗ FAIL - Could not get admin token${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Admin logged in successfully${NC}"
echo "  Token: ${ADMIN_TOKEN:0:50}..."

echo "Logging in as alice..."
ALICE_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login-json \
    -H 'Content-Type: application/json' \
    -d '{"username": "alice", "password": "alice123"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ALICE_TOKEN" ]; then
    echo -e "${RED}✗ FAIL - Could not get alice token${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Alice logged in successfully${NC}"

# 4. Test /auth/me
echo -e "\n${YELLOW}=== 4. Get Current User ===${NC}"
test_endpoint "GET /auth/me (admin)" \
    "curl -s http://localhost:8000/auth/me \
    -H 'Authorization: Bearer $ADMIN_TOKEN'"

test_endpoint "GET /auth/me (alice)" \
    "curl -s http://localhost:8000/auth/me \
    -H 'Authorization: Bearer $ALICE_TOKEN'"

# 5. Test Upload File
echo -e "\n${YELLOW}=== 5. File Upload ===${NC}"
echo "Creating test file..."
echo "Test content by alice" > /tmp/test_alice.txt
echo "Test content by admin" > /tmp/test_admin.txt

echo "Uploading file as alice..."
UPLOAD_ALICE=$(curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $ALICE_TOKEN" \
    -F "file=@/tmp/test_alice.txt" \
    -F "tags=test,alice,demo")
echo "  Response: ${UPLOAD_ALICE:0:100}..."

echo "Uploading file as admin..."
UPLOAD_ADMIN=$(curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F "file=@/tmp/test_admin.txt" \
    -F "tags=test,admin,important")
echo "  Response: ${UPLOAD_ADMIN:0:100}..."

sleep 3

# 6. Test List Files
echo -e "\n${YELLOW}=== 6. List Files ===${NC}"
test_endpoint "GET /files (admin - see all)" \
    "curl -s http://localhost:8000/files \
    -H 'Authorization: Bearer $ADMIN_TOKEN'"

test_endpoint "GET /files (alice - see only hers)" \
    "curl -s http://localhost:8000/files \
    -H 'Authorization: Bearer $ALICE_TOKEN'"

test_endpoint "GET /files?tags=test (filtered)" \
    "curl -s 'http://localhost:8000/files?tags=test' \
    -H 'Authorization: Bearer $ADMIN_TOKEN'"

# 7. Test Tags
echo -e "\n${YELLOW}=== 7. Get Tags ===${NC}"
test_endpoint "GET /tags (admin)" \
    "curl -s http://localhost:8000/tags \
    -H 'Authorization: Bearer $ADMIN_TOKEN'"

test_endpoint "GET /tags (alice)" \
    "curl -s http://localhost:8000/tags \
    -H 'Authorization: Bearer $ALICE_TOKEN'"

# 8. Test Stats
echo -e "\n${YELLOW}=== 8. Get Statistics ===${NC}"
test_endpoint "GET /stats (admin)" \
    "curl -s http://localhost:8000/stats \
    -H 'Authorization: Bearer $ADMIN_TOKEN'"

test_endpoint "GET /stats (alice)" \
    "curl -s http://localhost:8000/stats \
    -H 'Authorization: Bearer $ALICE_TOKEN'"

# 9. Test Download
echo -e "\n${YELLOW}=== 9. File Download ===${NC}"
echo "Getting file ID from alice's upload..."
FILE_ID=$(echo "$UPLOAD_ALICE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('url', '').split('/')[-1])" 2>/dev/null)

if [ ! -z "$FILE_ID" ]; then
    echo "Downloading file $FILE_ID..."
    curl -s "http://localhost:8000/files/$FILE_ID" \
        -H "Authorization: Bearer $ALICE_TOKEN" \
        -o /tmp/downloaded_file.txt
    
    if [ -f /tmp/downloaded_file.txt ]; then
        echo -e "${GREEN}✓ File downloaded successfully${NC}"
        echo "  Content: $(cat /tmp/downloaded_file.txt)"
    else
        echo -e "${RED}✗ Download failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipped - No file ID available${NC}"
fi

# Summary
echo -e "\n=========================================="
echo -e "${GREEN}TESTS COMPLETED${NC}"
echo "=========================================="
echo ""
echo "Frontend available at: http://localhost"
echo "API Gateway at: http://localhost:8000"
echo ""
echo "Test users:"
echo "  - admin / 123456 (is_admin=1)"
echo "  - alice / alice123 (is_admin=0)"
echo "  - bob / bob123 (is_admin=0)"
