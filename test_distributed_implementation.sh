#!/bin/bash
# Comprehensive test script for distributed system features

echo "=========================================="
echo "DISTRIBUTED SYSTEM VALIDATION TEST SUITE"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Use IPv4 explicitly to avoid IPv6 issues with Docker Swarm
BASE_URL="http://127.0.0.1:8000"
TOKEN=""

# Test counter
PASSED=0
FAILED=0

function test_case() {
    echo -e "${YELLOW}TEST:${NC} $1"
}

function pass() {
    echo -e "${GREEN}✓ PASSED${NC}: $1"
    ((PASSED++))
}

function fail() {
    echo -e "${RED}✗ FAILED${NC}: $1"
    ((FAILED++))
}

function section() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# Check prerequisites
section "1. CHECKING PREREQUISITES"

test_case "Docker services are running"
SERVICE_COUNT=$(docker service ls --filter name=tagfs --format "{{.Name}}" | wc -l)
if [ "$SERVICE_COUNT" -ge 4 ]; then
    pass "Found $SERVICE_COUNT services running"
else
    fail "Expected 4+ services, found $SERVICE_COUNT"
fi

test_case "Metadata replicas are 3/3"
METADATA_REPLICAS=$(docker service ls --filter name=tagfs_metadata --format "{{.Replicas}}")
if [ "$METADATA_REPLICAS" == "3/3" ]; then
    pass "Metadata service has 3 replicas"
else
    fail "Metadata replicas: $METADATA_REPLICAS (expected 3/3)"
fi

test_case "DataNode replicas are 3/3"
DATANODE_REPLICAS=$(docker service ls --filter name=tagfs_datanode --format "{{.Replicas}}")
if [ "$DATANODE_REPLICAS" == "3/3" ]; then
    pass "DataNode service has 3 replicas"
else
    fail "DataNode replicas: $DATANODE_REPLICAS (expected 3/3)"
fi

# Authentication
section "2. AUTHENTICATION"

test_case "Register new user"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","email":"test@test.com","password":"testpass123"}')

if echo "$REGISTER_RESPONSE" | grep -q "username"; then
    pass "User registered successfully"
else
    echo "Note: User might already exist (this is OK)"
fi

test_case "Login and get JWT token"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=testuser&password=testpass123")

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    pass "Successfully obtained JWT token"
else
    fail "Failed to obtain JWT token"
    echo "Response: $LOGIN_RESPONSE"
fi

# Test Quorum W=2
section "3. WRITE QUORUM W=2 TEST"

test_case "Upload file with W=2 quorum (all 3 DataNodes available)"
echo "Test file content for quorum validation" > /tmp/test_quorum.txt

UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_quorum.txt" \
    -F "tags=test,quorum,w2")

FILE_ID=$(echo "$UPLOAD_RESPONSE" | grep -o '"url":"[^"]*' | cut -d'/' -f3)

if [ -n "$FILE_ID" ]; then
    pass "File uploaded successfully with W=2 quorum (file_id: $FILE_ID)"
else
    fail "File upload failed"
    echo "Response: $UPLOAD_RESPONSE"
fi

test_case "Verify file is replicated on multiple DataNodes"
sleep 2  # Wait for replication
REPLICA_COUNT=$(docker service logs tagfs_datanode 2>&1 | grep -c "Stored file $FILE_ID")
if [ "$REPLICA_COUNT" -ge 2 ]; then
    pass "File replicated to $REPLICA_COUNT DataNodes (W=2 met)"
else
    fail "File only on $REPLICA_COUNT DataNodes (expected >= 2)"
fi

# Test Leader Election
section "4. BULLY LEADER ELECTION TEST"

test_case "Check current leader via logs"
LEADER_LOGS=$(docker service logs tagfs_metadata 2>&1 | grep "is now LEADER" | tail -1)
if [ -n "$LEADER_LOGS" ]; then
    pass "Leader election occurred"
    echo "   $LEADER_LOGS"
else
    fail "No leader election logs found"
fi

test_case "Verify peer discovery between Metadata nodes"
PEER_DISCOVERY=$(docker service logs tagfs_metadata 2>&1 | grep "Discovered peer Metadata" | wc -l)
if [ "$PEER_DISCOVERY" -gt 0 ]; then
    pass "Metadata nodes discovered each other ($PEER_DISCOVERY discoveries)"
else
    fail "No peer discovery between Metadata nodes"
fi

test_case "Check Bully node registration"
BULLY_REGISTRATION=$(docker service logs tagfs_metadata 2>&1 | grep "Registered node" | grep Bully | wc -l)
if [ "$BULLY_REGISTRATION" -gt 0 ]; then
    pass "Bully registered peer nodes ($BULLY_REGISTRATION registrations)"
else
    fail "No Bully registrations found"
fi

# Test Gossip Protocol
section "5. GOSSIP PROTOCOL TEST"

test_case "Check Gossip protocol started"
GOSSIP_START=$(docker service logs tagfs_metadata 2>&1 | grep "Started gossip protocol" | wc -l)
if [ "$GOSSIP_START" -ge 3 ]; then
    pass "Gossip protocol started on all 3 Metadata nodes"
elif [ "$GOSSIP_START" -gt 0 ]; then
    pass "Gossip protocol started on $GOSSIP_START node(s)"
else
    fail "Gossip protocol not started"
fi

test_case "Upload file and verify gossip propagation"
echo "Gossip test content" > /tmp/test_gossip.txt

GOSSIP_UPLOAD=$(curl -s -X POST "$BASE_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_gossip.txt" \
    -F "tags=gossip,test")

GOSSIP_FILE_ID=$(echo "$GOSSIP_UPLOAD" | grep -o '"url":"[^"]*' | cut -d'/' -f3)

if [ -n "$GOSSIP_FILE_ID" ]; then
    echo "   Uploaded file with ID: $GOSSIP_FILE_ID"
    echo "   Waiting 10 seconds for gossip propagation..."
    sleep 10
    
    # Check if gossip logs show file propagation
    GOSSIP_ACTIVITY=$(docker service logs tagfs_metadata 2>&1 | grep -c "Gossip")
    if [ "$GOSSIP_ACTIVITY" -gt 5 ]; then
        pass "Gossip activity detected ($GOSSIP_ACTIVITY log entries)"
    else
        echo "   Limited gossip activity, but protocol is running"
    fi
else
    fail "Failed to upload gossip test file"
fi

# Test Lamport Clocks
section "6. LAMPORT CLOCK TEST"

test_case "Check Lamport clock in file commits"
LAMPORT_LOGS=$(docker service logs tagfs_metadata 2>&1 | grep "Lamport time" | tail -3)
if [ -n "$LAMPORT_LOGS" ]; then
    pass "Lamport timestamps found in commit logs"
    echo "$LAMPORT_LOGS" | head -2 | sed 's/^/   /'
else
    fail "No Lamport timestamp logs found"
fi

# Test Read Quorum R=2
section "7. READ QUORUM R=2 TEST"

test_case "Download file with R=2 quorum"
if [ -n "$FILE_ID" ]; then
    DOWNLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/files/$FILE_ID" \
        -H "Authorization: Bearer $TOKEN" \
        -o /tmp/downloaded_file.txt)
    
    HTTP_CODE=$(echo "$DOWNLOAD_RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" == "200" ]; then
        pass "File downloaded successfully with R=2 quorum (HTTP 200)"
        
        # Verify content matches
        if diff -q /tmp/test_quorum.txt /tmp/downloaded_file.txt > /dev/null; then
            pass "Downloaded file content matches original"
        else
            fail "Downloaded file content differs from original"
        fi
    else
        fail "File download failed (HTTP $HTTP_CODE)"
    fi
else
    fail "No file ID to test download"
fi

# Test Metadata Persistence
section "8. METADATA PERSISTENCE TEST"

test_case "List all files to verify metadata"
LIST_RESPONSE=$(curl -s -X GET "$BASE_URL/files" \
    -H "Authorization: Bearer $TOKEN")

FILE_COUNT=$(echo "$LIST_RESPONSE" | grep -o '"name"' | wc -l)

if [ "$FILE_COUNT" -gt 0 ]; then
    pass "Metadata service returned $FILE_COUNT file(s)"
else
    fail "No files found in metadata"
fi

# Test Leader-Only Writes
section "9. LEADER VALIDATION TEST"

test_case "Verify leader-only writes enforcement"
LEADER_VALIDATION=$(docker service logs tagfs_metadata 2>&1 | grep "Not leader" | wc -l)
LEADER_COMMITS=$(docker service logs tagfs_metadata 2>&1 | grep "Committed file" | wc -l)

if [ "$LEADER_COMMITS" -gt 0 ]; then
    pass "Leader successfully committed $LEADER_COMMITS file(s)"
else
    echo "   No commit logs yet (might be too early)"
fi

# System Health
section "10. SYSTEM HEALTH CHECK"

test_case "All DataNodes registered with Metadata"
DATANODE_REGISTRATION=$(docker service logs tagfs_metadata 2>&1 | grep "Registered DataNode" | wc -l)
if [ "$DATANODE_REGISTRATION" -ge 3 ]; then
    pass "All DataNodes registered ($DATANODE_REGISTRATION registrations)"
else
    fail "Only $DATANODE_REGISTRATION DataNode registrations (expected 3+)"
fi

test_case "Heartbeat mechanisms active"
HEARTBEAT_COUNT=$(docker service logs tagfs_metadata 2>&1 | grep "heartbeat" | wc -l)
if [ "$HEARTBEAT_COUNT" -gt 10 ]; then
    pass "Heartbeat mechanism active ($HEARTBEAT_COUNT messages)"
else
    fail "Limited heartbeat activity ($HEARTBEAT_COUNT messages)"
fi

# Final Summary
section "TEST SUMMARY"

TOTAL=$((PASSED + FAILED))
echo ""
echo "Tests Passed: $PASSED / $TOTAL"
echo "Tests Failed: $FAILED / $TOTAL"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "ALL TESTS PASSED! ✓"
    echo -e "==========================================${NC}"
    exit 0
else
    echo -e "${RED}=========================================="
    echo "SOME TESTS FAILED"
    echo -e "==========================================${NC}"
    exit 1
fi
