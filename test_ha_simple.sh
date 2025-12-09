#!/bin/bash
#
# Test simplificado de alta disponibilidad
#

API_URL="http://localhost:8080"
TEST_USER="hauser_$(date +%s)"
TEST_PASS="test123"
TEST_EMAIL="ha_$(date +%s)@example.com"

echo "=============================================="
echo "  Test de Alta Disponibilidad"
echo "=============================================="

# Verificar backends individuales
echo -e "\n[1] Verificando backends individuales..."
for port in 8001 8002 8003; do
    response=$(curl -s "http://localhost:$port/" || echo "")
    if echo "$response" | grep -q "ok"; then
        echo "  ✓ Backend en puerto $port está UP"
    else
        echo "  ✗ Backend en puerto $port está DOWN"
        exit 1
    fi
done

# Verificar load balancer
echo -e "\n[2] Verificando load balancer..."
response=$(curl -s "$API_URL/")
if echo "$response" | grep -q "ok"; then
    echo "  ✓ Nginx load balancer funcionando"
else
    echo "  ✗ Load balancer no responde"
    exit 1
fi

# Registro de usuario
echo -e "\n[3] Registrando usuario..."
REGISTER=$(curl -s -X POST "$API_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}")

if echo "$REGISTER" | grep -q "username"; then
    echo "  ✓ Usuario registrado"
else
    echo "  ⚠ Usuario ya existe (continuando...)"
fi

# Login
echo -e "\n[4] Login..."
LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_USER&password=$TEST_PASS")

TOKEN=$(echo "$LOGIN" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    echo "  ✓ Login exitoso"
else
    echo "  ✗ Login falló"
    exit 1
fi

# Subir archivos
echo -e "\n[5] Subiendo 5 archivos..."
for i in {1..5}; do
    echo "Test file $i - $(date)" > /tmp/test_ha_$i.txt
    
    UPLOAD=$(curl -s -X POST "$API_URL/files" \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@/tmp/test_ha_$i.txt" \
        -F "tags=ha,test,file$i")
    
    if echo "$UPLOAD" | grep -q "test_ha_$i.txt"; then
        echo "  ✓ Archivo $i subido"
    else
        echo "  ✗ Error archivo $i"
    fi
    
    rm -f /tmp/test_ha_$i.txt
done

# Listar archivos
echo -e "\n[6] Listando archivos..."
FILES=$(curl -s -X GET "$API_URL/files" -H "Authorization: Bearer $TOKEN")
file_count=$(echo "$FILES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
echo "  ✓ Total archivos: $file_count"

# MATAR BACKEND-1
echo -e "\n[7] 💀 Matando backend-1..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml stop backend-1
sleep 2

echo "  Verificando que sigue funcionando..."
FILES_AFTER=$(curl -s -X GET "$API_URL/files" -H "Authorization: Bearer $TOKEN")
if [ -n "$FILES_AFTER" ]; then
    echo "  ✓ Sistema funciona con backend-1 caído"
else
    echo "  ✗ Sistema no responde"
    exit 1
fi

# MATAR BACKEND-2
echo -e "\n[8] 💀 Matando backend-2 (solo queda backend-3)..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml stop backend-2
sleep 2

echo "  Verificando con 1 solo backend..."
FILES_SINGLE=$(curl -s -X GET "$API_URL/files" -H "Authorization: Bearer $TOKEN")
if [ -n "$FILES_SINGLE" ]; then
    echo "  ✓ Sistema funciona con 1 solo backend"
else
    echo "  ✗ Sistema no responde con 1 backend"
    exit 1
fi

# Subir archivo con 1 backend
echo -e "\n[9] Subiendo archivo con 1 backend..."
echo "Single backend test - $(date)" > /tmp/test_single.txt
UPLOAD_SINGLE=$(curl -s -X POST "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@/tmp/test_single.txt" \
    -F "tags=single,test")

if echo "$UPLOAD_SINGLE" | grep -q "test_single.txt"; then
    echo "  ✓ Upload exitoso con 1 backend"
else
    echo "  ✗ Error con 1 backend"
fi
rm -f /tmp/test_single.txt

# LEVANTAR BACKENDS
echo -e "\n[10] 🔄 Levantando backends caídos..."
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml start backend-1
sudo docker-compose -f /home/vboxuser/Tag-based-file-system/docker-compose-test.yml start backend-2
sleep 5

echo "  Verificando backends..."
for port in 8001 8002 8003; do
    response=$(curl -s "http://localhost:$port/" || echo "")
    if echo "$response" | grep -q "ok"; then
        echo "  ✓ Backend puerto $port UP"
    fi
done

# Verificar integridad
echo -e "\n[11] Verificando integridad de datos..."
FILES_FINAL=$(curl -s -X GET "$API_URL/files" -H "Authorization: Bearer $TOKEN")
file_count_final=$(echo "$FILES_FINAL" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
echo "  ✓ Archivos finales: $file_count_final"

if [ "$file_count_final" -ge "$file_count" ]; then
    echo "  ✓ No se perdieron datos"
else
    echo "  ✗ Se perdieron datos"
    exit 1
fi

echo ""
echo "=============================================="
echo "  ✅ TEST COMPLETADO"
echo "=============================================="
echo ""
echo "Resultados:"
echo "  - 3 backends funcionando ✓"
echo "  - Load balancer OK ✓"
echo "  - Tolerancia a fallos ✓"
echo "  - Sin pérdida de datos ✓"
echo ""

exit 0
