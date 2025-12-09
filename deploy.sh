#!/bin/bash
#
# Script maestro de despliegue del sistema distribuido
# Automatiza todo el proceso de configuración y despliegue
#
# USO:
#   En Manager: sudo bash deploy.sh manager <IP_MANAGER> <DB_PASSWORD>
#   En Worker:  sudo bash deploy.sh worker <IP_MANAGER>
#
# Ejemplo:
#   sudo bash deploy.sh manager 172.20.10.4 mi_password_segura
#   sudo bash deploy.sh worker 172.20.10.4
#

set -e

ROLE="$1"
NFS_SERVER_IP="$2"
DB_PASSWORD="$3"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

show_usage() {
    echo "Uso:"
    echo "  En Manager: sudo bash deploy.sh manager <IP_MANAGER> <DB_PASSWORD>"
    echo "  En Worker:  sudo bash deploy.sh worker <IP_MANAGER>"
    echo ""
    echo "Ejemplo:"
    echo "  sudo bash deploy.sh manager 172.20.10.4 mi_password_segura"
    echo "  sudo bash deploy.sh worker 172.20.10.4"
    exit 1
}

# Validar argumentos
if [ -z "$ROLE" ] || [ -z "$NFS_SERVER_IP" ]; then
    show_usage
fi

if [ "$ROLE" = "manager" ] && [ -z "$DB_PASSWORD" ]; then
    print_error "Se requiere DB_PASSWORD para el nodo manager"
    show_usage
fi

echo "=========================================="
echo "  Sistema Distribuido - Despliegue"
echo "=========================================="
echo "Rol:          $ROLE"
echo "NFS Server:   $NFS_SERVER_IP"
if [ "$ROLE" = "manager" ]; then
    echo "DB Password:  ${DB_PASSWORD:0:3}***"
fi
echo "=========================================="
echo ""

# ==========================================
# MANAGER: Configuración completa
# ==========================================
if [ "$ROLE" = "manager" ]; then
    print_step "Configurando nodo MANAGER..."
    
    # 1. Configurar servidor NFS
    print_step "1/8 - Configurando servidor NFS..."
    if [ -f "setup-nfs-server.sh" ]; then
        bash setup-nfs-server.sh
    else
        print_error "setup-nfs-server.sh no encontrado"
        exit 1
    fi
    
    # 2. Copiar datos existentes a NFS
    print_step "2/8 - Migrando datos existentes a NFS..."
    if [ -d "tags_data" ]; then
        cp -r tags_data/* /srv/nfs/tagfs_data/ 2>/dev/null || true
        print_success "Datos copiados a /srv/nfs/tagfs_data/"
    else
        print_warning "Directorio tags_data no encontrado"
        mkdir -p /srv/nfs/tagfs_data/files
        echo "{}" > /srv/nfs/tagfs_data/files/files.json
    fi
    
    # 3. Inicializar Docker Swarm si no está inicializado
    print_step "3/8 - Verificando Docker Swarm..."
    if ! docker info | grep -q "Swarm: active"; then
        print_step "Inicializando Docker Swarm..."
        docker swarm init --advertise-addr "$NFS_SERVER_IP" 2>/dev/null || true
        print_success "Docker Swarm inicializado"
    else
        print_success "Docker Swarm ya está activo"
    fi
    
    # 4. Obtener token de worker
    print_step "4/8 - Obteniendo token de worker..."
    WORKER_TOKEN=$(docker swarm join-token worker -q)
    echo ""
    echo "=========================================="
    echo "  TOKEN PARA WORKERS"
    echo "=========================================="
    echo "Ejecuta en los nodos workers:"
    echo ""
    echo "  docker swarm join --token $WORKER_TOKEN $NFS_SERVER_IP:2377"
    echo ""
    echo "=========================================="
    echo ""
    
    # 5. Construir imágenes
    print_step "5/8 - Construyendo imágenes Docker..."
    
    if [ -f "Dockerfile.backend" ]; then
        print_step "Construyendo tagfs-backend..."
        docker build -t tagfs-backend:latest -f Dockerfile.backend .
        print_success "Backend construido"
    fi
    
    if [ -d "frontend-react" ] && [ -f "frontend-react/Dockerfile" ]; then
        print_step "Construyendo tagfs-frontend..."
        cd frontend-react
        docker build --build-arg VITE_API_URL="http://${NFS_SERVER_IP}:8000" -t tagfs-frontend:latest .
        cd ..
        print_success "Frontend construido"
    fi
    
    # 6. Exportar variables de entorno
    print_step "6/8 - Configurando variables de entorno..."
    export NFS_SERVER_IP="$NFS_SERVER_IP"
    export DB_PASSWORD="$DB_PASSWORD"
    print_success "Variables exportadas"
    
    # 7. Desplegar stack
    print_step "7/8 - Desplegando stack en Docker Swarm..."
    if [ -f "docker-stack-distributed.yml" ]; then
        docker stack deploy -c docker-stack-distributed.yml tagfs
        print_success "Stack desplegado"
    else
        print_error "docker-stack-distributed.yml no encontrado"
        exit 1
    fi
    
    # 8. Esperar a que servicios estén listos y ejecutar migración
    print_step "8/8 - Esperando a que PostgreSQL esté listo..."
    echo "Esperando 45 segundos para que PostgreSQL arranque..."
    sleep 45
    
    # Verificar que PostgreSQL está listo
    print_step "Verificando estado de PostgreSQL..."
    MAX_RETRIES=10
    RETRY=0
    POSTGRES_READY=false
    
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if docker service logs tagfs_database 2>&1 | grep -q "database system is ready to accept connections"; then
            POSTGRES_READY=true
            print_success "PostgreSQL está listo"
            break
        fi
        RETRY=$((RETRY + 1))
        echo "  Intento $RETRY/$MAX_RETRIES..."
        sleep 5
    done
    
    if [ "$POSTGRES_READY" = true ]; then
        # Migrar datos automáticamente
        print_step "Migrando datos de SQLite a PostgreSQL..."
        export DATABASE_URL="postgresql://tagfs_user:${DB_PASSWORD}@localhost:5432/tagfs"
        
        if [ -f "migrate_sqlite_to_postgres.py" ]; then
            python3 migrate_sqlite_to_postgres.py
            print_success "✅ Migración de datos completada"
            
            # Optimizar PostgreSQL
            print_step "Optimizando índices en PostgreSQL..."
            if [ -f "optimize_postgres.py" ]; then
                python3 optimize_postgres.py
                print_success "✅ Base de datos optimizada"
            else
                print_warning "optimize_postgres.py no encontrado, saltando optimización"
            fi
        else
            print_warning "migrate_sqlite_to_postgres.py no encontrado, migración manual requerida"
        fi
    else
        print_warning "PostgreSQL no respondió a tiempo. Ejecuta la migración manualmente:"
        echo "  export DATABASE_URL=\"postgresql://tagfs_user:${DB_PASSWORD}@localhost:5432/tagfs\""
        echo "  python3 migrate_sqlite_to_postgres.py"
        echo "  python3 optimize_postgres.py"
    fi
    
    # Verificar servicios finales
    print_step "Verificando servicios desplegados..."
    docker service ls
    
    echo ""
    print_success "=========================================="
    print_success "  ✅ MANAGER CONFIGURADO"
    print_success "=========================================="
    echo ""
    echo "🌐 URLs de acceso:"
    echo "   Frontend: http://${NFS_SERVER_IP}:3000"
    echo "   Backend:  http://${NFS_SERVER_IP}:8000"
    echo "   API Docs: http://${NFS_SERVER_IP}:8000/docs"
    echo ""
    echo "🔑 Credenciales por defecto (si se creó admin):"
    echo "   Usuario:  admin"
    echo "   Password: admin123"
    echo ""
    echo "📊 Comandos útiles:"
    echo "   Ver logs:         docker service logs -f tagfs_backend"
    echo "   Ver nodos:        docker node ls"
    echo "   Escalar backend:  docker service scale tagfs_backend=5"
    echo "   Reiniciar:        docker service update --force tagfs_backend"
    echo ""
    echo "=========================================="
    echo ""

# ==========================================
# WORKER: Configuración cliente
# ==========================================
elif [ "$ROLE" = "worker" ]; then
    print_step "Configurando nodo WORKER..."
    
    # 1. Configurar cliente NFS
    print_step "1/3 - Configurando cliente NFS..."
    if [ -f "setup-nfs-client.sh" ]; then
        bash setup-nfs-client.sh "$NFS_SERVER_IP"
    else
        print_error "setup-nfs-client.sh no encontrado"
        exit 1
    fi
    
    # 2. Verificar que Docker está instalado
    print_step "2/3 - Verificando Docker..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker no está instalado"
        print_step "Instalando Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        print_success "Docker instalado"
    else
        print_success "Docker ya está instalado"
    fi
    
    # 3. Instrucciones para unirse al swarm
    print_step "3/3 - Listo para unirse al Swarm..."
    echo ""
    print_warning "=========================================="
    print_warning "  IMPORTANTE - Unirse al Swarm"
    print_warning "=========================================="
    echo "Ejecuta el comando que obtuviste del Manager:"
    echo ""
    echo "  docker swarm join --token <TOKEN> ${NFS_SERVER_IP}:2377"
    echo ""
    print_warning "=========================================="
    echo ""
    
    print_success "WORKER configurado correctamente"
    echo ""
    echo "Después de unirte al Swarm:"
    echo "1. Verifica en el Manager que el worker aparece:"
    echo "   docker node ls"
    echo ""
    echo "2. Los servicios se desplegarán automáticamente según placement constraints"
    echo ""

else
    print_error "Rol no válido: $ROLE (debe ser 'manager' o 'worker')"
    show_usage
fi

echo ""
print_success "✅ Configuración completada"
