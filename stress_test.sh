#!/bin/bash
#
# Script de stress test para sistema distribuido
#
# Simula múltiples clientes accediendo simultáneamente:
# - Uploads concurrentes
# - Búsquedas simultáneas
# - Modificaciones de tags
#
# Uso: bash stress_test.sh <API_URL> <NUM_CLIENTS>

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# ==========================================
# Configuración
# ==========================================

API_URL="${1:-http://localhost:8000}"
NUM_CLIENTS="${2:-10}"
DURATION="${3:-30}"  # segundos

echo "=========================================="
echo "  Stress Test del Sistema Distribuido"
echo "=========================================="
echo "API URL: $API_URL"
echo "Clientes concurrentes: $NUM_CLIENTS"
echo "Duración: ${DURATION}s"
echo ""

# Variables para tracking
TOTAL_REQUESTS=0
SUCCESSFUL_REQUESTS=0
FAILED_REQUESTS=0

# ==========================================
# Función: Cliente simulado
# ==========================================

run_client() {
    local client_id=$1
    local start_time=$(date +%s)
    local end_time=$((start_time + DURATION))
    
    # Registrar usuario único
    local username="stress_user_${client_id}_$$"
    local password="test123"
    
    local register_response=$(curl -s -X POST "$API_URL/register" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$username\",\"email\":\"$username@test.com\",\"password\":\"$password\"}" \
        2>/dev/null)
    
    if ! echo "$register_response" | grep -q "username"; then
        echo "ERROR: Cliente $client_id - registro falló"
        return 1
    fi
    
    # Login
    local login_response=$(curl -s -X POST "$API_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$username\",\"password\":\"$password\"}" \
        2>/dev/null)
    
    local token=$(echo "$login_response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$token" ]; then
        echo "ERROR: Cliente $client_id - login falló"
        return 1
    fi
    
    local requests=0
    local errors=0
    
    # Loop de requests hasta que termine el tiempo
    while [ $(date +%s) -lt $end_time ]; do
        local action=$((RANDOM % 4))
        
        case $action in
            0)
                # Upload de archivo
                local filename="stress_file_${client_id}_${requests}.txt"
                echo "Stress test data from client $client_id request $requests" > "/tmp/$filename"
                
                local upload_response=$(curl -s -X POST "$API_URL/files" \
                    -H "Authorization: Bearer $token" \
                    -F "file=@/tmp/$filename" \
                    -F "tags=stress,client${client_id},request${requests}" \
                    2>/dev/null)
                
                rm -f "/tmp/$filename"
                
                if echo "$upload_response" | grep -q "name"; then
                    ((requests++))
                else
                    ((errors++))
                fi
                ;;
            
            1)
                # Listar archivos
                local list_response=$(curl -s -X GET "$API_URL/files" \
                    -H "Authorization: Bearer $token" \
                    2>/dev/null)
                
                if echo "$list_response" | grep -q "\["; then
                    ((requests++))
                else
                    ((errors++))
                fi
                ;;
            
            2)
                # Búsqueda por tags
                local search_response=$(curl -s -X GET "$API_URL/files?tags=stress" \
                    -H "Authorization: Bearer $token" \
                    2>/dev/null)
                
                if echo "$search_response" | grep -q "\["; then
                    ((requests++))
                else
                    ((errors++))
                fi
                ;;
            
            3)
                # Obtener estadísticas
                local stats_response=$(curl -s -X GET "$API_URL/stats" \
                    -H "Authorization: Bearer $token" \
                    2>/dev/null)
                
                if echo "$stats_response" | grep -q "total_files"; then
                    ((requests++))
                else
                    ((errors++))
                fi
                ;;
        esac
        
        # Pequeño delay aleatorio (10-100ms)
        sleep 0.0$((RANDOM % 10))
    done
    
    echo "$requests $errors"
}

# ==========================================
# Ejecutar clientes en paralelo
# ==========================================

print_info "Iniciando $NUM_CLIENTS clientes concurrentes..."
echo ""

# Crear directorio temporal para resultados
TEMP_DIR=$(mktemp -d)

# Lanzar clientes en background
for i in $(seq 1 $NUM_CLIENTS); do
    (
        result=$(run_client $i)
        echo "$result" > "$TEMP_DIR/client_$i.txt"
    ) &
done

# Mostrar progreso
print_info "Clientes ejecutándose... (${DURATION}s)"
for i in $(seq 1 $DURATION); do
    echo -n "."
    sleep 1
done
echo ""

# Esperar a que todos terminen
print_info "Esperando a que terminen todos los clientes..."
wait

echo ""
print_info "Recopilando resultados..."

# Sumar resultados
total_requests=0
total_errors=0

for i in $(seq 1 $NUM_CLIENTS); do
    if [ -f "$TEMP_DIR/client_$i.txt" ]; then
        read requests errors < "$TEMP_DIR/client_$i.txt"
        total_requests=$((total_requests + requests))
        total_errors=$((total_errors + errors))
    fi
done

# Cleanup
rm -rf "$TEMP_DIR"

# ==========================================
# Resultados
# ==========================================

echo ""
echo "=========================================="
echo "  📊 RESULTADOS DEL STRESS TEST"
echo "=========================================="
echo ""
echo "Configuración:"
echo "  - Clientes concurrentes: $NUM_CLIENTS"
echo "  - Duración: ${DURATION}s"
echo ""
echo "Resultados:"
echo "  - Total requests: $total_requests"
echo "  - Requests exitosos: $((total_requests - total_errors))"
echo "  - Requests fallidos: $total_errors"
echo ""

if [ $total_requests -gt 0 ]; then
    success_rate=$((100 * (total_requests - total_errors) / total_requests))
    rps=$((total_requests / DURATION))
    
    echo "Métricas:"
    echo "  - Tasa de éxito: ${success_rate}%"
    echo "  - Requests/segundo: ~${rps}"
    echo ""
    
    if [ $success_rate -ge 95 ]; then
        print_success "✅ Sistema soporta bien la carga concurrente"
    elif [ $success_rate -ge 80 ]; then
        print_warn "⚠️  Sistema funcional pero con algunas fallas"
    else
        print_error "❌ Sistema tiene problemas bajo carga"
    fi
else
    print_error "❌ No se pudieron ejecutar requests"
fi

echo ""
echo "=========================================="
echo ""

# Verificar estado de servicios si estamos en el manager
if command -v docker &> /dev/null; then
    if docker service ls 2>/dev/null | grep -q tagfs; then
        echo "Estado de servicios Docker:"
        docker service ls --filter "name=tagfs"
        echo ""
    fi
fi

echo "💡 Tip: Revisa los logs para más detalles:"
echo "   docker service logs -f tagfs_backend"
echo ""

exit 0
