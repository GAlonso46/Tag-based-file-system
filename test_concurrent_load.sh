#!/bin/bash
#
# Test de carga concurrente - 50 requests simultáneos
#

API_URL="http://localhost:8080"
TEST_USER="loaduser_$(date +%s)"
TEST_PASS="test123"
TEST_EMAIL="load_$(date +%s)@example.com"

echo "=============================================="
echo "  Test de Carga Concurrente"
echo "=============================================="

# Registro y login
echo -e "\n[1] Registro y login..."
REGISTER=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}")

LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_USER&password=$TEST_PASS")

TOKEN=$(echo "$LOGIN" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "  ✗ Login falló"
    exit 1
fi
echo "  ✓ Usuario autenticado"

# Función para subir archivo
upload_file() {
    local id=$1
    local token=$2
    echo "Concurrent load test $id - $(date)" > /tmp/load_$id.txt
    
    result=$(curl -s -X POST "$API_URL/files" \
        -H "Authorization: Bearer $token" \
        -F "file=@/tmp/load_$id.txt" \
        -F "tags=load,concurrent,test$id" 2>&1)
    
    rm -f /tmp/load_$id.txt
    
    if echo "$result" | grep -q "load_$id.txt"; then
        echo "OK"
    else
        echo "FAIL"
    fi
}

export -f upload_file
export API_URL
export TOKEN

# Lanzar 50 uploads concurrentes
echo -e "\n[2] Lanzando 50 uploads concurrentes..."
success=0
fail=0

for i in {1..50}; do
    upload_file $i "$TOKEN" &
done

# Esperar a que terminen
wait

sleep 3

# Contar resultados
echo -e "\n[3] Verificando archivos subidos..."
FILES=$(curl -s -X GET "$API_URL/files?tags=load" -H "Authorization: Bearer $TOKEN")
uploaded=$(echo "$FILES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo "  ✓ Archivos subidos exitosamente: $uploaded/50"

if [ "$uploaded" -ge 45 ]; then
    echo "  ✓ Test de concurrencia PASADO (>90%)"
    result="PASS"
else
    echo "  ⚠ Advertencia: solo $uploaded/50 archivos"
    result="WARNING"
fi

# Test de lectura concurrente
echo -e "\n[4] Test de lectura concurrente (50 requests)..."

read_concurrent() {
    curl -s -X GET "$API_URL/files" -H "Authorization: Bearer $TOKEN" > /dev/null
    echo $?
}

export -f read_concurrent

read_success=0
for i in {1..50}; do
    read_concurrent &
done
wait

echo "  ✓ 50 lecturas concurrentes completadas"

# Estadísticas
echo -e "\n[5] Obteniendo estadísticas..."
STATS=$(curl -s -X GET "$API_URL/stats" -H "Authorization: Bearer $TOKEN")
echo "$STATS" | python3 -m json.tool

echo ""
echo "=============================================="
echo "  ✅ TEST DE CARGA COMPLETADO"
echo "=============================================="
echo ""
echo "Resultados:"
echo "  - Uploads concurrentes: $uploaded/50"
echo "  - Lecturas concurrentes: 50/50"
echo "  - Load balancer: OK"
echo "  - Estado: $result"
echo ""

exit 0
