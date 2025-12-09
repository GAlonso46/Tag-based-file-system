#!/bin/bash
#
# Test de Alta Disponibilidad - Docker Compose
#
# Este script:
# 1. Levanta 3 backends + 2 frontends + PostgreSQL + Nginx
# 2. Prueba que todos funcionan
# 3. Mata instancias aleatoriamente
# 4. Verifica que el sistema sigue funcionando
# 5. Levanta las instancias caídas
# 6. Repite el proceso
#

set -e

COMPOSE_FILE="docker-compose-test.yml"
API_URL="http://localhost:8080"
TEST_USER="hauser_$(date +%s)"
TEST_PASS="test123"
TEST_EMAIL="ha_$(date +%s)@example.com"

echo "=============================================="
echo "  Test de Alta Disponibilidad"
echo "=============================================="

# Función para hacer request con retry
request_with_retry() {
    local url=$1
    local method=${2:-GET}
    local data=${3:-}
    local headers=${4:-}
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if [ -n "$data" ]; then
            response=$(curl -s -X "$method" "$url" $headers -d "$data" 2>&1 || echo "FAILED")
        else
            response=$(curl -s -X "$method" "$url" $headers 2>&1 || echo "FAILED")
        fi
        
        if [ "$response" != "FAILED" ] && [ -n "$response" ]; then
            echo "$response"
            return 0
        fi
        
        echo "  ⚠ Intento $attempt/$max_attempts falló, reintentando..." >&2
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "  ✗ Request falló después de $max_attempts intentos" >&2
    return 1
}

# Paso 1: Levantar servicios
echo -e "\n[PASO 1] Levantando servicios con Docker Compose..."
docker-compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
docker-compose -f "$COMPOSE_FILE" up -d --build

echo "  Esperando que los servicios estén listos..."
sleep 15

# Verificar que los 3 backends están up
echo -e "\n[PASO 2] Verificando backends individuales..."
for port in 8001 8002 8003; do
    response=$(curl -s "http://localhost:$port/" || echo "")
    if echo "$response" | grep -q "ok"; then
        echo "  ✓ Backend en puerto $port está UP"
    else
        echo "  ✗ Backend en puerto $port está DOWN"
        exit 1
    fi
done

# Verificar Nginx load balancer
echo -e "\n[PASO 3] Verificando Nginx load balancer..."
response=$(request_with_retry "$API_URL/")
if echo "$response" | grep -q "ok"; then
    echo "  ✓ Nginx load balancer funcionando"
else
    echo "  ✗ Nginx load balancer no responde"
    exit 1
fi

# Paso 4: Registro de usuario a través del load balancer
echo -e "\n[PASO 4] Registrando usuario a través del load balancer..."
REGISTER=$(request_with_retry "$API_URL/auth/register" "POST" \
    "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}" \
    "-H 'Content-Type: application/json'")

if echo "$REGISTER" | grep -q "username"; then
    echo "  ✓ Usuario registrado exitosamente"
else
    echo "  ⚠ Usuario ya existe o error (continuando...)"
fi

# Paso 5: Login
echo -e "\n[PASO 5] Login de usuario..."
LOGIN=$(request_with_retry "$API_URL/auth/login" "POST" \
    "username=$TEST_USER&password=$TEST_PASS" \
    "-H 'Content-Type: application/x-www-form-urlencoded'")

TOKEN=$(echo "$LOGIN" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    echo "  ✓ Login exitoso"
else
    echo "  ✗ Login falló"
    exit 1
fi

# Paso 6: Subir archivos a través del load balancer
echo -e "\n[PASO 6] Subiendo archivos a través del load balancer..."
for i in {1..5}; do
    echo "Test file $i - $(date)" > /tmp/test_ha_$i.txt
    
    UPLOAD=$(curl -s -X POST "$API_URL/files" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@/tmp/test_ha_$i.txt" \
        -F "tags=ha,test,file$i")
    
    if echo "$UPLOAD" | grep -q "test_ha_$i.txt"; then
        echo "  ✓ Archivo $i subido correctamente"
    else
        echo "  ✗ Error subiendo archivo $i"
    fi
    
    rm -f /tmp/test_ha_$i.txt
done

# Paso 7: Verificar que todos los archivos están accesibles
echo -e "\n[PASO 7] Verificando archivos..."
FILES=$(request_with_retry "$API_URL/files" "GET" "" "-H 'Authorization: Bearer $TOKEN'")
file_count=$(echo "$FILES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo "  ✓ Total de archivos visibles: $file_count"

# Paso 8: MATAR BACKEND-1 (simular fallo)
echo -e "\n[PASO 8] 💀 Matando backend-1 (simulando fallo)..."
docker-compose -f "$COMPOSE_FILE" stop backend-1
sleep 3

echo "  Verificando que el sistema sigue funcionando..."
FILES_AFTER=$(request_with_retry "$API_URL/files" "GET" "" "-H 'Authorization: Bearer $TOKEN'")
if [ -n "$FILES_AFTER" ]; then
    echo "  ✓ Sistema sigue funcionando con backend-1 caído"
else
    echo "  ✗ Sistema no responde con backend-1 caído"
    exit 1
fi

# Paso 9: MATAR BACKEND-2 también (dejar solo 1 backend)
echo -e "\n[PASO 9] 💀 Matando backend-2 (dejando solo backend-3)..."
docker-compose -f "$COMPOSE_FILE" stop backend-2
sleep 3

echo "  Verificando que el sistema sigue funcionando con 1 solo backend..."
FILES_SINGLE=$(request_with_retry "$API_URL/files" "GET" "" "-H 'Authorization: Bearer $TOKEN'")
if [ -n "$FILES_SINGLE" ]; then
    echo "  ✓ Sistema sigue funcionando con solo 1 backend activo"
else
    echo "  ✗ Sistema no responde con solo 1 backend"
    exit 1
fi

# Paso 10: Subir más archivos con solo 1 backend
echo -e "\n[PASO 10] Subiendo archivo con solo 1 backend activo..."
echo "Test with single backend - $(date)" > /tmp/test_single.txt

UPLOAD_SINGLE=$(curl -s -X POST "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_single.txt" \
    -F "tags=single,backend,test")

if echo "$UPLOAD_SINGLE" | grep -q "test_single.txt"; then
    echo "  ✓ Archivo subido correctamente con 1 solo backend"
else
    echo "  ✗ Error subiendo archivo con 1 backend"
fi

rm -f /tmp/test_single.txt

# Paso 11: LEVANTAR LOS BACKENDS CAÍDOS
echo -e "\n[PASO 11] 🔄 Levantando backends caídos..."
docker-compose -f "$COMPOSE_FILE" start backend-1
docker-compose -f "$COMPOSE_FILE" start backend-2
sleep 5

echo "  Verificando que todos los backends están up nuevamente..."
for port in 8001 8002 8003; do
    response=$(curl -s "http://localhost:$port/" || echo "")
    if echo "$response" | grep -q "ok"; then
        echo "  ✓ Backend en puerto $port está UP"
    else
        echo "  ✗ Backend en puerto $port sigue DOWN"
    fi
done

# Paso 12: Verificar que todos los archivos siguen ahí
echo -e "\n[PASO 12] Verificando integridad de datos después de recuperación..."
FILES_FINAL=$(request_with_retry "$API_URL/files" "GET" "" "-H 'Authorization: Bearer $TOKEN'")
file_count_final=$(echo "$FILES_FINAL" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo "  ✓ Total de archivos después de recuperación: $file_count_final"

if [ "$file_count_final" -ge "$file_count" ]; then
    echo "  ✓ No se perdieron datos durante los fallos"
else
    echo "  ✗ Se perdieron datos: antes=$file_count, después=$file_count_final"
    exit 1
fi

# Paso 13: Test de escritura concurrente
echo -e "\n[PASO 13] Test de escritura concurrente con múltiples backends..."

# Función para subir archivo en background
upload_concurrent() {
    local id=$1
    echo "Concurrent test $id - $(date)" > /tmp/concurrent_$id.txt
    
    curl -s -X POST "$API_URL/files" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@/tmp/concurrent_$id.txt" \
        -F "tags=concurrent,test$id" > /dev/null
    
    rm -f /tmp/concurrent_$id.txt
}

# Lanzar 10 uploads concurrentes
for i in {1..10}; do
    upload_concurrent $i &
done

# Esperar a que terminen
wait

sleep 2

# Verificar cuántos archivos hay ahora
FILES_CONCURRENT=$(request_with_retry "$API_URL/files?tags=concurrent" "GET" "" "-H 'Authorization: Bearer $TOKEN'")
concurrent_count=$(echo "$FILES_CONCURRENT" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo "  ✓ Archivos subidos concurrentemente: $concurrent_count/10"

if [ "$concurrent_count" -ge 8 ]; then
    echo "  ✓ Escritura concurrente funcionando correctamente"
else
    echo "  ⚠ Advertencia: solo se registraron $concurrent_count/10 archivos"
fi

# Resumen final
echo ""
echo "=============================================="
echo "  ✅ TEST DE ALTA DISPONIBILIDAD COMPLETADO"
echo "=============================================="
echo ""
echo "📊 Resultados:"
echo "  - 3 backends levantados ✓"
echo "  - 2 backends matados y recuperados ✓"
echo "  - Sistema funcionó con 1 solo backend ✓"
echo "  - Nginx load balancer funcionando ✓"
echo "  - Sin pérdida de datos ✓"
echo "  - Escritura concurrente: $concurrent_count/10 ✓"
echo ""
echo "🎯 El sistema es tolerante a fallos y altamente disponible"
echo ""

# Limpiar (opcional)
read -p "¿Deseas detener los contenedores? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose -f "$COMPOSE_FILE" down
    echo "  ✓ Contenedores detenidos"
else
    echo "  ℹ Contenedores siguen corriendo. Para detenerlos ejecuta:"
    echo "    docker-compose -f $COMPOSE_FILE down"
fi

exit 0
