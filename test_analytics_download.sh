#!/bin/bash
# Test de Analytics y Download

set -e

echo "=========================================="
echo "TEST: Analytics y Download"
echo "=========================================="

# Login
echo "Logging in as admin..."
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login-json \
    -H 'Content-Type: application/json' \
    -d '{"username": "admin", "password": "123456"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
    echo "❌ Login failed"
    exit 1
fi
echo "✅ Logged in"

# Upload test files
echo ""
echo "Uploading test files..."
echo "Test document content" > /tmp/test_doc.txt
echo "Test image content" > /tmp/test_img.jpg

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_doc.txt" \
    -F "tags=document,test,work" > /dev/null

curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_img.jpg" \
    -F "tags=image,test,personal" > /dev/null

echo "✅ Files uploaded"

sleep 3

# Test Analytics Endpoints
echo ""
echo "=== Testing Analytics Endpoints ==="

echo -n "1. Files by date... "
RESULT=$(curl -s "http://localhost:8000/analytics/files-by-date?days=7" -H "Authorization: Bearer $TOKEN")
if [[ "$RESULT" == *"data"* ]]; then
    echo "✅ PASS"
    echo "   $RESULT"
else
    echo "❌ FAIL: $RESULT"
fi

echo -n "2. Files by type... "
RESULT=$(curl -s "http://localhost:8000/analytics/files-by-type" -H "Authorization: Bearer $TOKEN")
if [[ "$RESULT" == *"data"* ]]; then
    echo "✅ PASS"
    echo "   $RESULT"
else
    echo "❌ FAIL: $RESULT"
fi

echo -n "3. Tags usage... "
RESULT=$(curl -s "http://localhost:8000/analytics/tags-usage" -H "Authorization: Bearer $TOKEN")
if [[ "$RESULT" == *"data"* ]]; then
    echo "✅ PASS"
    echo "   $RESULT"
else
    echo "❌ FAIL: $RESULT"
fi

echo -n "4. Storage by tag... "
RESULT=$(curl -s "http://localhost:8000/analytics/storage-by-tag" -H "Authorization: Bearer $TOKEN")
if [[ "$RESULT" == *"data"* ]]; then
    echo "✅ PASS"
    echo "   $RESULT"
else
    echo "❌ FAIL: $RESULT"
fi

echo -n "5. User stats... "
RESULT=$(curl -s "http://localhost:8000/analytics/user-stats" -H "Authorization: Bearer $TOKEN")
if [[ "$RESULT" == *"data"* ]]; then
    echo "✅ PASS"
    echo "   $RESULT"
else
    echo "❌ FAIL: $RESULT"
fi

# Test Download with file ID
echo ""
echo "=== Testing Download with file_id ==="
FILES=$(curl -s http://localhost:8000/files -H "Authorization: Bearer $TOKEN")
FILE_ID=$(echo "$FILES" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if len(data) > 0 else '')" 2>/dev/null)

if [ ! -z "$FILE_ID" ]; then
    echo "Testing download for file_id: $FILE_ID"
    HTTP_CODE=$(curl -s -o /tmp/downloaded_test.txt -w "%{http_code}" \
        "http://localhost:8000/files/$FILE_ID" \
        -H "Authorization: Bearer $TOKEN")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Download successful (HTTP 200)"
        echo "   Content: $(cat /tmp/downloaded_test.txt | head -c 50)"
    else
        echo "❌ Download failed (HTTP $HTTP_CODE)"
    fi
else
    echo "⚠️  No files available to test download"
fi

echo ""
echo "=========================================="
echo "✅ TEST COMPLETED"
echo "=========================================="
echo ""
echo "You can now test the Analytics UI at:"
echo "http://localhost (click Analytics tab)"
