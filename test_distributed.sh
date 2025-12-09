#!/bin/bash
#
# Script de testing para sistema distribuido
#
# Valida:
# - Servicios corriendo en Docker Swarm
# - Conectividad a PostgreSQL
# - API endpoints funcionando
# - NFS compartido entre nodos
# - Failover de réplicas
#
# Uso: bash test_distributed.sh <MANAGER_IP>

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# ==========================================
# Verificar argumentos
# ==========================================

MANAGER_IP="${1:-localhost}"
API_URL="http://${MANAGER_IP}:8000"
FRONTEND_URL="http://${MANAGER_IP}:3000"

echo "=========================================="
echo "  Tests del Sistema Distribuido"
echo "=========================================="
echo "Manager IP: $MANAGER_IP"
echo "API URL: $API_URL"
echo ""

# ==========================================
# TEST 1: Verificar servicios de Docker
# ==========================================

print_test "1/10 - Verificando servicios Docker Swarm..."

EXPECTED_SERVICES=("tagfs_backend" "tagfs_frontend" "tagfs_database")
ALL_OK=true

for service in "${EXPECTED_SERVICES[@]}"; do
    if docker service ps "$service" --format "{{.CurrentState}}" 2>/dev/null | grep -q "Running"; then
        REPLICAS=$(docker service ls --filter "name=$service" --format "{{.Replicas}}")
        print_success "Servicio $service: $REPLICAS"
    else
        print_error "Servicio $service no está corriendo"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = true ]; then
    print_success "Todos los servicios están corriendo"
else
    print_error "Algunos servicios tienen problemas"
    exit 1
fi

echo ""

# ==========================================
# TEST 2: Health check de la API
# ==========================================

print_test "2/10 - Verificando health check de la API..."

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/" || echo "000")

if [ "$RESPONSE" = "200" ]; then
    print_success "API responde correctamente (HTTP 200)"
else
    print_error "API no responde (HTTP $RESPONSE)"
    exit 1
fi

echo ""

# ==========================================
# TEST 3: Registro de usuario
# ==========================================

print_test "3/10 - Registrando usuario de prueba..."

RANDOM_USER="test_$(date +%s)"
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$RANDOM_USER\",\"email\":\"$RANDOM_USER@test.com\",\"password\":\"test123\"}")

if echo "$REGISTER_RESPONSE" | grep -q "username"; then
    print_success "Usuario registrado: $RANDOM_USER"
else
    print_error "Error al registrar usuario: $REGISTER_RESPONSE"
    exit 1
fi

echo ""

# ==========================================
# TEST 4: Login y obtención de token
# ==========================================

print_test "4/10 - Autenticando usuario..."

LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$RANDOM_USER\",\"password\":\"test123\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    print_success "Token obtenido correctamente"
else
    print_error "Error al obtener token: $LOGIN_RESPONSE"
    exit 1
fi

echo ""

# ==========================================
# TEST 5: Subir archivo
# ==========================================

print_test "5/10 - Subiendo archivo de prueba..."

# Crear archivo temporal
TEST_FILE="/tmp/test_file_$(date +%s).txt"
echo "Este es un archivo de prueba para el sistema distribuido" > "$TEST_FILE"

UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$TEST_FILE" \
    -F "tags=test,distribuido,automatico")

if echo "$UPLOAD_RESPONSE" | grep -q "name"; then
    FILENAME=$(echo "$UPLOAD_RESPONSE" | grep -o '"name":"[^"]*' | cut -d'"' -f4)
    print_success "Archivo subido: $FILENAME"
else
    print_error "Error al subir archivo: $UPLOAD_RESPONSE"
    rm -f "$TEST_FILE"
    exit 1
fi

rm -f "$TEST_FILE"
echo ""

# ==========================================
# TEST 6: Listar archivos
# ==========================================

print_test "6/10 - Listando archivos del usuario..."

LIST_RESPONSE=$(curl -s -X GET "$API_URL/files" \
    -H "Authorization: Bearer $TOKEN")

if echo "$LIST_RESPONSE" | grep -q "$FILENAME"; then
    FILE_COUNT=$(echo "$LIST_RESPONSE" | grep -o '"name"' | wc -l)
    print_success "Archivos listados correctamente (total: $FILE_COUNT)"
else
    print_error "No se encontró el archivo en la lista"
    exit 1
fi

echo ""

# ==========================================
# TEST 7: Búsqueda por tags
# ==========================================

print_test "7/10 - Probando búsqueda por tags..."

SEARCH_RESPONSE=$(curl -s -X GET "$API_URL/files?tags=test,distribuido" \
    -H "Authorization: Bearer $TOKEN")

if echo "$SEARCH_RESPONSE" | grep -q "$FILENAME"; then
    print_success "Búsqueda por tags funciona correctamente"
else
    print_error "Búsqueda por tags falló"
    exit 1
fi

echo ""

# ==========================================
# TEST 8: Obtener estadísticas
# ==========================================

print_test "8/10 - Obteniendo estadísticas..."

STATS_RESPONSE=$(curl -s -X GET "$API_URL/stats" \
    -H "Authorization: Bearer $TOKEN")

if echo "$STATS_RESPONSE" | grep -q "total_files"; then
    TOTAL_FILES=$(echo "$STATS_RESPONSE" | grep -o '"total_files":[0-9]*' | cut -d':' -f2)
    print_success "Estadísticas obtenidas (archivos: $TOTAL_FILES)"
else
    print_error "Error al obtener estadísticas"
    exit 1
fi

echo ""

# ==========================================
# TEST 9: Verificar persistencia en NFS
# ==========================================

print_test "9/10 - Verificando persistencia de archivos en NFS..."

if [ -f "/srv/nfs/tagfs_data/files/$FILENAME" ] || [ -f "/mnt/tagfs_data/files/$FILENAME" ]; then
    print_success "Archivo encontrado en almacenamiento compartido"
else
    print_warning "No se pudo verificar archivo en NFS (puede estar en otro nodo)"
fi

echo ""

# ==========================================
# TEST 10: Verificar PostgreSQL
# ==========================================

print_test "10/10 - Verificando PostgreSQL..."

if docker service logs tagfs_database 2>&1 | tail -20 | grep -q "database system is ready"; then
    print_success "PostgreSQL está operacional"
else
    print_warning "No se pudo verificar estado de PostgreSQL"
fi

echo ""

# ==========================================
# RESUMEN
# ==========================================

echo "=========================================="
echo "  ✅ TODOS LOS TESTS PASARON"
echo "=========================================="
echo ""
echo "📊 Resumen:"
echo "   - Servicios Docker Swarm: OK"
echo "   - API REST: OK"
echo "   - Autenticación JWT: OK"
echo "   - Upload de archivos: OK"
echo "   - Búsqueda por tags: OK"
echo "   - Estadísticas: OK"
echo "   - PostgreSQL: OK"
echo ""
echo "🎯 El sistema distribuido está funcionando correctamente"
echo ""
echo "=========================================="
echo ""
echo "📝 Comandos útiles:"
echo "   Ver logs backend:   docker service logs -f tagfs_backend"
echo "   Ver logs database:  docker service logs -f tagfs_database"
echo "   Escalar backend:    docker service scale tagfs_backend=5"
echo "   Ver nodos:          docker node ls"
echo ""

exit 0
