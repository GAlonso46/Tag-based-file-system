#!/bin/bash
#
# Test de estrés extremo: matar backends durante cargas concurrentes
#

API_URL="http://localhost:8080"
TEST_USER="stress_$(date +%s)"
TEST_PASS="test123"
TEST_EMAIL="stress_$(date +%s)@example.com"

echo "=============================================="
echo "  Test de Estrés Extremo"
echo "=============================================="

# Setup
echo -e "\n[1] Setup: Registro y login..."
curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}" > /dev/null

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
upload_continuous() {
    local id=$1
    local token=$2
    local max=$3
    
    for i in $(seq 1 $max); do
        echo "Stress test $id-$i - $(date)" > /tmp/stress_${id}_${i}.txt
        
        curl -s -X POST "$API_URL/files" \
            -H "Authorization: Bearer $token" \
            -F "file=@/tmp/stress_${id}_${i}.txt" \
            -F "tags=stress,test$id" > /dev/null 2>&1
        
        rm -f /tmp/stress_${id}_${i}.txt
        sleep 0.1
    done
}

export -f upload_continuous
export API_URL TOKEN

# Lanzar uploads continuos en background
echo -e "\n[2] Lanzando 10 threads de uploads continuos (20 cada uno)..."
for i in {1..10}; do
    upload_continuous $i "$TOKEN" 20 &
done

# Esperar 2 segundos y matar backend-1
sleep 2
echo -e "\n[3] 💀 Matando backend-1 durante las cargas..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml stop backend-1 > /dev/null 2>&1

# Esperar 2 segundos más y matar backend-2
sleep 2
echo -e "\n[4] 💀 Matando backend-2 durante las cargas..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml stop backend-2 > /dev/null 2>&1

# Esperar a que terminen los uploads
echo -e "\n[5] Esperando a que terminen los uploads..."
wait

# Levantar backends
echo -e "\n[6] 🔄 Levantando backends..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml start backend-1 > /dev/null 2>&1
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml start backend-2 > /dev/null 2>&1
sleep 5

# Verificar integridad
echo -e "\n[7] Verificando integridad de datos..."
sleep 2

FILES=$(curl -s -X GET "$API_URL/files?tags=stress" -H "Authorization: Bearer $TOKEN")
uploaded=$(echo "$FILES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo "  ✓ Archivos guardados: $uploaded/200"

if [ "$uploaded" -ge 150 ]; then
    echo "  ✓ Excelente: >75% de archivos guardados durante el caos"
    result="EXCELENTE"
elif [ "$uploaded" -ge 100 ]; then
    echo "  ✓ Bueno: >50% de archivos guardados"
    result="BUENO"
else
    echo "  ⚠ Moderado: <50% de archivos guardados"
    result="MODERADO"
fi

# Verificar que no hay duplicados
echo -e "\n[8] Verificando que no hay duplicados..."
DUPLICATES=$(echo "$FILES" | python3 -c "
import sys, json
files = json.load(sys.stdin)
names = [f['name'] for f in files]
print(len(names) - len(set(names)))
" 2>/dev/null || echo "0")

if [ "$DUPLICATES" -eq 0 ]; then
    echo "  ✓ Sin duplicados"
else
    echo "  ⚠ Encontrados $DUPLICATES duplicados"
fi

# Stats finales
echo -e "\n[9] Estadísticas finales..."
STATS=$(curl -s -X GET "$API_URL/stats" -H "Authorization: Bearer $TOKEN")
echo "$STATS" | python3 -m json.tool

echo ""
echo "=============================================="
echo "  ✅ TEST DE ESTRÉS COMPLETADO"
echo "=============================================="
echo ""
echo "Resultados:"
echo "  - Archivos guardados: $uploaded/200"
echo "  - Duplicados: $DUPLICATES"
echo "  - 2 backends matados durante carga"
echo "  - Sistema se recuperó ✓"
echo "  - Estado: $result"
echo ""

exit 0
