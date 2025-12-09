#!/bin/bash
#
# Test completo del API REST
#

set -e  # Exit on error

API_URL="http://localhost:8000"
TEST_USER="testuser"
TEST_PASS="test123"
TEST_EMAIL="test@example.com"

echo "======================================"
echo "  Test de Endpoints del API REST"
echo "======================================"

# Test 1: Health check
echo -e "\n[TEST 1] Health check..."
HEALTH=$(curl -s "$API_URL/")
echo "$HEALTH" | python3 -m json.tool
if echo "$HEALTH" | grep -q "ok"; then
    echo "  ✓ API respondiendo correctamente"
else
    echo "  ✗ API no responde"
    exit 1
fi

# Test 2: Registro de usuario
echo -e "\n[TEST 2] Registro de usuario..."
REGISTER=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}")

echo "$REGISTER" | python3 -m json.tool
if echo "$REGISTER" | grep -q "username"; then
    echo "  ✓ Usuario registrado correctamente"
else
    echo "  ⚠ Usuario ya existe o error (continuando...)"
fi

# Test 3: Login
echo -e "\n[TEST 3] Login de usuario..."
LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_USER&password=$TEST_PASS")

echo "$LOGIN" | python3 -m json.tool

TOKEN=$(echo "$LOGIN" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    echo "  ✓ Login exitoso, token obtenido"
else
    echo "  ✗ Login falló"
    exit 1
fi

# Test 4: Subir archivo
echo -e "\n[TEST 4] Subir archivo con tags..."
echo "Contenido de prueba para el test del API" > /tmp/test_file.txt

UPLOAD=$(curl -s -X POST "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_file.txt" \
    -F "tags=test,api,backend")

echo "$UPLOAD" | python3 -m json.tool

if echo "$UPLOAD" | grep -q "test_file.txt"; then
    echo "  ✓ Archivo subido correctamente"
else
    echo "  ✗ Error subiendo archivo"
    exit 1
fi

# Test 5: Listar archivos
echo -e "\n[TEST 5] Listar archivos..."
FILES=$(curl -s -X GET "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN")

echo "$FILES" | python3 -m json.tool

if echo "$FILES" | grep -q "test_file.txt"; then
    echo "  ✓ Archivo aparece en la lista"
else
    echo "  ✗ Archivo no encontrado en la lista"
    exit 1
fi

# Test 6: Buscar por tags
echo -e "\n[TEST 6] Buscar archivos por tags..."
SEARCH=$(curl -s -X GET "$API_URL/files?tags=test" \
    -H "Authorization: Bearer $TOKEN")

echo "$SEARCH" | python3 -m json.tool

if echo "$SEARCH" | grep -q "test_file.txt"; then
    echo "  ✓ Búsqueda por tags funciona"
else
    echo "  ✗ Búsqueda por tags falló"
    exit 1
fi

# Test 7: Obtener tags
echo -e "\n[TEST 7] Listar todos los tags..."
TAGS=$(curl -s -X GET "$API_URL/tags" \
    -H "Authorization: Bearer $TOKEN")

echo "$TAGS" | python3 -m json.tool

if echo "$TAGS" | grep -q "test"; then
    echo "  ✓ Tags listados correctamente"
else
    echo "  ✗ Error listando tags"
    exit 1
fi

# Test 8: Estadísticas
echo -e "\n[TEST 8] Obtener estadísticas..."
STATS=$(curl -s -X GET "$API_URL/stats" \
    -H "Authorization: Bearer $TOKEN")

echo "$STATS" | python3 -m json.tool

if echo "$STATS" | grep -q "total_files"; then
    echo "  ✓ Estadísticas obtenidas correctamente"
else
    echo "  ✗ Error obteniendo estadísticas"
    exit 1
fi

# Test 9: Eliminar archivo
echo -e "\n[TEST 9] Eliminar archivo..."
DELETE=$(curl -s -X DELETE "$API_URL/files/test_file.txt" \
    -H "Authorization: Bearer $TOKEN")

echo "$DELETE" | python3 -m json.tool

if echo "$DELETE" | grep -q "eliminado"; then
    echo "  ✓ Archivo eliminado correctamente"
else
    echo "  ✗ Error eliminando archivo"
    exit 1
fi

# Test 10: Verificar eliminación
echo -e "\n[TEST 10] Verificar que el archivo fue eliminado..."
FILES_AFTER=$(curl -s -X GET "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN")

if echo "$FILES_AFTER" | grep -q "test_file.txt"; then
    echo "  ✗ El archivo aún existe"
    exit 1
else
    echo "  ✓ Archivo eliminado correctamente"
fi

# Cleanup
rm -f /tmp/test_file.txt

echo ""
echo "======================================"
echo "  ✅ TODOS LOS TESTS PASARON"
echo "======================================"
echo ""
echo "📝 Endpoints probados:"
echo "  - GET / (health check)"
echo "  - POST /auth/register"
echo "  - POST /auth/login"
echo "  - POST /files (upload)"
echo "  - GET /files (list)"
echo "  - GET /files?tags=X (search)"
echo "  - GET /tags"
echo "  - GET /stats"
echo "  - DELETE /files/{filename}"
echo ""
echo "🎯 El API está funcionando correctamente"
echo ""

exit 0
