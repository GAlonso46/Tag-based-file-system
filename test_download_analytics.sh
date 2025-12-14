#!/bin/bash
# Test de download y analytics

set -e

echo "=========================================="
echo "TEST DE DOWNLOAD Y ANALYTICS"
echo "=========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Login como admin
echo "1. Login como admin..."
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login-json \
    -H 'Content-Type: application/json' \
    -d '{"username": "admin", "password": "123456"}' | \
    python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ADMIN_TOKEN" ]; then
    echo -e "${RED}✗ FAIL - No se pudo obtener token${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Token obtenido${NC}"

# Subir archivo de prueba
echo ""
echo "2. Subiendo archivo de prueba..."
echo "Contenido de prueba para download" > /tmp/test_download.txt
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/files \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F "file=@/tmp/test_download.txt" \
    -F "tags=test,download")

FILE_ID=$(echo "$UPLOAD_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('url', '').split('/')[-1])" 2>/dev/null)

if [ -z "$FILE_ID" ]; then
    echo -e "${RED}✗ FAIL - No se pudo subir archivo${NC}"
    echo "Response: $UPLOAD_RESPONSE"
    exit 1
fi
echo -e "${GREEN}✓ Archivo subido con ID: $FILE_ID${NC}"

# Probar download con header Authorization
echo ""
echo "3. Descargando archivo con Authorization header..."
curl -s "http://localhost:8000/files/$FILE_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -o /tmp/downloaded.txt

if [ -f /tmp/downloaded.txt ]; then
    CONTENT=$(cat /tmp/downloaded.txt)
    if [ "$CONTENT" == "Contenido de prueba para download" ]; then
        echo -e "${GREEN}✓ Archivo descargado correctamente${NC}"
        echo "  Contenido: $CONTENT"
    else
        echo -e "${RED}✗ FAIL - Contenido incorrecto${NC}"
        echo "  Esperado: 'Contenido de prueba para download'"
        echo "  Obtenido: '$CONTENT'"
    fi
else
    echo -e "${RED}✗ FAIL - No se descargó el archivo${NC}"
fi

# Probar endpoints de analytics
echo ""
echo "4. Probando endpoints de analytics..."

echo -n "   /analytics/files-by-date... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/analytics1.json "http://localhost:8000/analytics/files-by-date?days=30" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓${NC}"
    echo "      $(cat /tmp/analytics1.json | python3 -c 'import sys, json; d=json.load(sys.stdin); print(f"Total: {d.get(\"total\", 0)} archivos")' 2>/dev/null)"
else
    echo -e "${RED}✗ (HTTP $RESPONSE)${NC}"
fi

echo -n "   /analytics/files-by-type... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/analytics2.json "http://localhost:8000/analytics/files-by-type" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓${NC}"
    cat /tmp/analytics2.json | python3 -c 'import sys, json; d=json.load(sys.stdin); print("      Tipos:", ", ".join(d.get("labels", [])))' 2>/dev/null
else
    echo -e "${RED}✗ (HTTP $RESPONSE)${NC}"
fi

echo -n "   /analytics/tags-usage... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/analytics3.json "http://localhost:8000/analytics/tags-usage" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓${NC}"
    cat /tmp/analytics3.json | python3 -c 'import sys, json; d=json.load(sys.stdin); print("      Tags:", len(d.get("labels", [])))' 2>/dev/null
else
    echo -e "${RED}✗ (HTTP $RESPONSE)${NC}"
fi

echo -n "   /analytics/storage-by-tag... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/analytics4.json "http://localhost:8000/analytics/storage-by-tag" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ (HTTP $RESPONSE)${NC}"
fi

echo -n "   /analytics/user-stats... "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/analytics5.json "http://localhost:8000/analytics/user-stats" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓${NC}"
    cat /tmp/analytics5.json | python3 -c 'import sys, json; d=json.load(sys.stdin); print("      Usuarios:", len(d.get("labels", [])))' 2>/dev/null
else
    echo -e "${RED}✗ (HTTP $RESPONSE)${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}TESTS COMPLETADOS${NC}"
echo "=========================================="
echo ""
echo "Frontend disponible en: http://localhost"
echo "  - Login con: admin / 123456"
echo "  - Ir a Analytics para ver gráficas"
