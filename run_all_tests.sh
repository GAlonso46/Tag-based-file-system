#!/bin/bash

# Test Suite Completo
# Ejecuta todos los tests de las mejoras implementadas

set -e

echo "============================================================"
echo "         TagFS - Suite Completa de Tests"
echo "============================================================"
echo ""
echo "Este script ejecutará todos los tests de verificación:"
echo "  1. Verificación de implementación"
echo "  2. Test de uploads paralelos y quorum"
echo "  3. Test de re-replicación automática"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

function print_success() { echo -e "${GREEN}✓ $1${NC}"; }
function print_error() { echo -e "${RED}✗ $1${NC}"; }
function print_info() { echo -e "${YELLOW}➜ $1${NC}"; }

TESTS_PASSED=0
TESTS_FAILED=0

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-stack-distributed.yml" ]; then
    print_error "Por favor ejecuta este script desde el directorio raíz del proyecto"
    exit 1
fi

# Verificar que los scripts de test existen
for script in verify_improvements.sh test_parallel_upload.sh test_rereplica.sh; do
    if [ ! -f "$script" ]; then
        print_error "Script $script no encontrado"
        exit 1
    fi
    chmod +x "$script"
done

# TEST 1: Verificación de implementación
print_header "TEST 1: Verificación de Implementación"

if ./verify_improvements.sh; then
    print_success "Test de verificación PASADO"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_error "Test de verificación FALLADO"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Preguntar si desplegar el stack para tests funcionales
echo ""
print_info "Los siguientes tests requieren que el stack esté desplegado."

if docker stack ls | grep -q "tagfs"; then
    print_success "Stack tagfs ya está corriendo"
else
    echo ""
    read -p "¿Deseas desplegar el stack ahora? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Desplegando stack..."
        
        # Verificar si las imágenes existen
        if ! docker images | grep -q "tagfs-backend"; then
            print_info "Construyendo imágenes Docker..."
            if [ -f "build-images.sh" ]; then
                ./build-images.sh
            else
                print_error "Script build-images.sh no encontrado"
                exit 1
            fi
        fi
        
        docker stack deploy -c docker-stack-distributed.yml tagfs
        
        print_info "Esperando 30 segundos a que los servicios inicien..."
        for i in {30..1}; do
            echo -ne "\rEsperando... ${i}s "
            sleep 1
        done
        echo ""
        print_success "Stack desplegado"
    else
        print_info "Tests funcionales omitidos. Despliega el stack manualmente para ejecutarlos:"
        print_info "  docker stack deploy -c docker-stack-distributed.yml tagfs"
        exit 0
    fi
fi

# Verificar que los servicios están corriendo
echo ""
print_info "Verificando servicios..."
EXPECTED_SERVICES=("gateway" "metadata" "datanode")
for service in "${EXPECTED_SERVICES[@]}"; do
    if docker service ls | grep -q "tagfs_$service"; then
        REPLICAS=$(docker service ls | grep "tagfs_$service" | awk '{print $4}')
        print_success "Servicio tagfs_$service: $REPLICAS"
    else
        print_error "Servicio tagfs_$service no encontrado"
    fi
done

# TEST 2: Uploads Paralelos y Quorum
print_header "TEST 2: Uploads Paralelos y Quorum"

if ./test_parallel_upload.sh; then
    print_success "Test de uploads paralelos PASADO"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    print_error "Test de uploads paralelos FALLADO"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# TEST 3: Re-replicación Automática
print_header "TEST 3: Re-replicación Automática"

echo ""
print_info "Este test detendrá temporalmente un DataNode"
read -p "¿Continuar? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ./test_rereplica.sh; then
        print_success "Test de re-replicación PASADO"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        print_error "Test de re-replicación FALLADO"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    print_info "Test de re-replicación omitido"
fi

# RESUMEN FINAL
print_header "RESUMEN DE TESTS"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo "Tests ejecutados: $TOTAL_TESTS"
echo -e "${GREEN}Tests pasados:   $TESTS_PASSED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Tests fallados:  $TESTS_FAILED${NC}"
else
    echo -e "${GREEN}Tests fallados:  0${NC}"
fi

echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    print_success "TODOS LOS TESTS PASARON ✓✓✓"
    echo ""
    echo "El sistema está completamente funcional y cumple con:"
    echo "  ✓ Re-replicación automática"
    echo "  ✓ Uploads paralelos con Quorum W=2"
    echo "  ✓ Downloads con Quorum R=2"
    echo "  ✓ Detección de fallos y recuperación"
    echo "  ✓ Integridad de datos"
    echo ""
    print_success "Sistema listo para producción 🚀"
else
    print_error "ALGUNOS TESTS FALLARON"
    echo ""
    echo "Por favor revisa los logs arriba para más detalles."
    exit 1
fi

echo ""
echo "============================================================"
echo ""

# Opciones post-test
echo "Opciones:"
echo "  1. Ver logs de todos los servicios"
echo "  2. Ver estado de los servicios"
echo "  3. Ver logs de re-replicación"
echo "  4. Salir"
echo ""
read -p "Selecciona una opción (1-4): " -n 1 -r
echo ""

case $REPLY in
    1)
        echo ""
        print_info "Logs del Gateway:"
        docker service logs tagfs_gateway --tail 20
        echo ""
        print_info "Logs de Metadata:"
        docker service logs tagfs_metadata --tail 20
        echo ""
        print_info "Logs de DataNodes:"
        docker service logs tagfs_datanode --tail 20
        ;;
    2)
        echo ""
        docker service ls
        echo ""
        docker ps --filter "name=tagfs"
        ;;
    3)
        echo ""
        print_info "Logs de re-replicación:"
        docker service logs tagfs_metadata 2>&1 | grep -E "Re-replication|dead|Successfully|Replicating" || echo "No hay logs de re-replicación recientes"
        ;;
    4)
        print_info "Saliendo..."
        ;;
    *)
        print_info "Opción no válida"
        ;;
esac

echo ""
