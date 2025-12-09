#!/bin/bash
#
# Script de validación de configuración
# Verifica que todos los archivos necesarios existan y estén correctos
#
# No requiere Docker ni permisos especiales

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_ok() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

ERRORS=0
WARNINGS=0

echo "=========================================="
echo "  Validación de Configuración"
echo "=========================================="
echo ""

# ==========================================
# CHECK 1: Archivos Docker
# ==========================================

print_check "1/10 - Verificando archivos Docker..."

DOCKER_FILES=(
    "Dockerfile.backend"
    "docker-stack-distributed.yml"
    "frontend-react/Dockerfile"
)

for file in "${DOCKER_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_ok "$file existe"
    else
        print_fail "$file NO ENCONTRADO"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 2: Scripts de deployment
# ==========================================

print_check "2/10 - Verificando scripts de deployment..."

SCRIPTS=(
    "deploy.sh"
    "setup-nfs-server.sh"
    "setup-nfs-client.sh"
    "migrate_sqlite_to_postgres.py"
    "optimize_postgres.py"
    "test_distributed.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            print_ok "$script existe y es ejecutable"
        else
            print_warn "$script existe pero no es ejecutable"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        print_fail "$script NO ENCONTRADO"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 3: Código fuente del backend
# ==========================================

print_check "3/10 - Verificando código del backend..."

BACKEND_FILES=(
    "api/__init__.py"
    "api/main.py"
    "api/database.py"
    "api/models.py"
    "api/auth.py"
    "api/dependencies.py"
)

for file in "${BACKEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_ok "$file"
    else
        print_fail "$file NO ENCONTRADO"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 4: Código fuente del frontend
# ==========================================

print_check "4/10 - Verificando código del frontend..."

FRONTEND_FILES=(
    "frontend-react/package.json"
    "frontend-react/src/App.jsx"
    "frontend-react/src/main.jsx"
    "frontend-react/src/components/LoginPage.jsx"
)

for file in "${FRONTEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_ok "$file"
    else
        print_fail "$file NO ENCONTRADO"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 5: Documentación
# ==========================================

print_check "5/10 - Verificando documentación..."

DOCS=(
    "ESTRATEGIAS_SIN_DHT.md"
    "ARQUITECTURA_DETALLADA.md"
    "HOJA_DE_RUTA_DISTRIBUIDO.md"
    "README_DISTRIBUIDO.md"
    "ARCHIVOS_LEGACY.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        print_ok "$doc"
    else
        print_warn "$doc no encontrado"
        WARNINGS=$((WARNINGS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 6: Sintaxis Python
# ==========================================

print_check "6/10 - Verificando sintaxis Python..."

PYTHON_FILES=(
    "api/main.py"
    "api/database.py"
    "api/models.py"
    "migrate_sqlite_to_postgres.py"
    "optimize_postgres.py"
)

for file in "${PYTHON_FILES[@]}"; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        print_ok "$file - sintaxis correcta"
    else
        print_fail "$file - ERROR DE SINTAXIS"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ==========================================
# CHECK 7: Dependencies
# ==========================================

print_check "7/10 - Verificando requirements.txt..."

if [ -f "requirements.txt" ]; then
    # Verificar dependencias críticas
    CRITICAL_DEPS=("fastapi" "uvicorn" "sqlalchemy" "psycopg2-binary" "python-jose")
    
    for dep in "${CRITICAL_DEPS[@]}"; do
        if grep -q "$dep" requirements.txt; then
            print_ok "$dep incluido"
        else
            print_fail "$dep NO INCLUIDO en requirements.txt"
            ERRORS=$((ERRORS + 1))
        fi
    done
else
    print_fail "requirements.txt NO ENCONTRADO"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ==========================================
# CHECK 8: Variables de entorno en docker-stack
# ==========================================

print_check "8/10 - Verificando docker-stack-distributed.yml..."

if [ -f "docker-stack-distributed.yml" ]; then
    # Verificar que usa variables de entorno
    if grep -q "\${NFS_SERVER_IP}" docker-stack-distributed.yml; then
        print_ok "Variable NFS_SERVER_IP configurada"
    else
        print_warn "NFS_SERVER_IP no usa variable de entorno"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    if grep -q "\${DB_PASSWORD}" docker-stack-distributed.yml; then
        print_ok "Variable DB_PASSWORD configurada"
    else
        print_warn "DB_PASSWORD no usa variable de entorno"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # Verificar servicios definidos
    SERVICES=("backend" "frontend" "database")
    for service in "${SERVICES[@]}"; do
        if grep -q "  $service:" docker-stack-distributed.yml; then
            print_ok "Servicio '$service' definido"
        else
            print_fail "Servicio '$service' NO DEFINIDO"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

echo ""

# ==========================================
# CHECK 9: Datos de prueba
# ==========================================

print_check "9/10 - Verificando datos existentes..."

if [ -f "tags_data/files/files.json" ]; then
    FILE_COUNT=$(grep -o '":' tags_data/files/files.json | wc -l)
    print_ok "files.json existe ($FILE_COUNT archivos registrados)"
else
    print_warn "files.json no encontrado (se creará en despliegue)"
    WARNINGS=$((WARNINGS + 1))
fi

if [ -f "tags_data/users.db" ]; then
    print_ok "users.db existe (para migración)"
else
    print_warn "users.db no encontrado (se creará usuario admin por defecto)"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ==========================================
# CHECK 10: Archivos legacy movidos
# ==========================================

print_check "10/10 - Verificando limpieza de archivos legacy..."

if [ -d "_legacy" ]; then
    LEGACY_COUNT=$(find _legacy -type f | wc -l)
    print_ok "Carpeta _legacy existe ($LEGACY_COUNT archivos archivados)"
else
    print_warn "_legacy no encontrado"
    WARNINGS=$((WARNINGS + 1))
fi

# Verificar que archivos legacy fueron movidos
LEGACY_FILES=("main.py" "Dockerfile.cli" "docker-compose.yml")
for file in "${LEGACY_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_ok "$file removido/archivado correctamente"
    else
        print_warn "$file aún existe en raíz (debería estar en _legacy/)"
        WARNINGS=$((WARNINGS + 1))
    fi
done

echo ""

# ==========================================
# RESUMEN
# ==========================================

echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    print_ok "VALIDACIÓN EXITOSA"
    echo "=========================================="
    echo ""
    echo "✅ Todos los archivos críticos están presentes"
    echo "✅ No se encontraron errores de sintaxis"
    echo "✅ Configuración lista para despliegue"
    echo ""
    if [ $WARNINGS -gt 0 ]; then
        echo "⚠️  $WARNINGS advertencias encontradas (no críticas)"
    fi
    echo ""
    echo "Próximos pasos:"
    echo "  1. Revisar README_DISTRIBUIDO.md"
    echo "  2. Ejecutar: sudo bash deploy.sh manager <IP> <PASSWORD>"
    echo "  3. Ejecutar: bash test_distributed.sh <IP>"
    echo ""
    exit 0
else
    print_fail "VALIDACIÓN FALLÓ"
    echo "=========================================="
    echo ""
    echo "❌ $ERRORS errores encontrados"
    if [ $WARNINGS -gt 0 ]; then
        echo "⚠️  $WARNINGS advertencias encontradas"
    fi
    echo ""
    echo "Revisa los errores arriba y corrígelos antes de continuar"
    echo ""
    exit 1
fi
