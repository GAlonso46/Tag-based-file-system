#!/bin/bash
#
# Script de monitoreo en tiempo real del sistema distribuido
#
# Muestra:
# - Estado de servicios Docker Swarm
# - Distribución de réplicas en nodos
# - Logs en tiempo real
# - Métricas de uso
#
# Uso: bash monitor.sh [refresh_interval]

# Configuración
REFRESH_INTERVAL="${1:-5}"  # segundos

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Función para limpiar pantalla y mostrar header
show_header() {
    clear
    echo -e "${BLUE}=========================================="
    echo -e "  Sistema Distribuido - Monitor"
    echo -e "==========================================${NC}"
    echo -e "Actualización cada ${REFRESH_INTERVAL}s (Ctrl+C para salir)"
    echo ""
    date
    echo ""
}

# Función para verificar si Docker Swarm está activo
check_swarm() {
    if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
        echo -e "${RED}[✗] Docker Swarm no está activo${NC}"
        echo ""
        echo "Inicializa Docker Swarm primero:"
        echo "  docker swarm init --advertise-addr <IP>"
        exit 1
    fi
}

# Función para mostrar estado de nodos
show_nodes() {
    echo -e "${CYAN}📍 NODOS DEL CLUSTER${NC}"
    echo "────────────────────────────────────────"
    
    docker node ls --format "table {{.Hostname}}\t{{.Status}}\t{{.Availability}}\t{{.ManagerStatus}}" 2>/dev/null || echo "Error obteniendo nodos"
    echo ""
}

# Función para mostrar estado de servicios
show_services() {
    echo -e "${CYAN}🚀 SERVICIOS${NC}"
    echo "────────────────────────────────────────"
    
    docker service ls --filter "name=tagfs" --format "table {{.Name}}\t{{.Mode}}\t{{.Replicas}}\t{{.Image}}" 2>/dev/null || echo "No hay servicios tagfs"
    echo ""
}

# Función para mostrar distribución de réplicas
show_replicas() {
    echo -e "${CYAN}🔄 DISTRIBUCIÓN DE RÉPLICAS${NC}"
    echo "────────────────────────────────────────"
    
    for service in $(docker service ls --filter "name=tagfs" --format "{{.Name}}" 2>/dev/null); do
        echo -e "${GREEN}$service:${NC}"
        docker service ps "$service" --format "  {{.Node}}: {{.CurrentState}}" 2>/dev/null | head -10
        echo ""
    done
}

# Función para mostrar estadísticas de recursos
show_stats() {
    echo -e "${CYAN}💾 RECURSOS (promedio de containers)${NC}"
    echo "────────────────────────────────────────"
    
    # Obtener stats de containers tagfs
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        $(docker ps --filter "name=tagfs" -q) 2>/dev/null | grep -E "(CONTAINER|tagfs)" || echo "No hay containers activos"
    echo ""
}

# Función para mostrar logs recientes
show_recent_logs() {
    echo -e "${CYAN}📝 LOGS RECIENTES (últimas 5 líneas por servicio)${NC}"
    echo "────────────────────────────────────────"
    
    for service in tagfs_backend tagfs_frontend tagfs_database; do
        if docker service ls --filter "name=$service" --format "{{.Name}}" 2>/dev/null | grep -q "$service"; then
            echo -e "${GREEN}$service:${NC}"
            docker service logs --tail 5 --no-trunc "$service" 2>/dev/null | sed 's/^/  /' || echo "  (sin logs)"
            echo ""
        fi
    done
}

# Función para mostrar health checks
show_health() {
    echo -e "${CYAN}🏥 HEALTH CHECKS${NC}"
    echo "────────────────────────────────────────"
    
    # Verificar API
    if curl -s http://localhost:8000/ 2>/dev/null | grep -q "status"; then
        echo -e "  Backend API: ${GREEN}✓ OK${NC}"
    else
        echo -e "  Backend API: ${RED}✗ FAIL${NC}"
    fi
    
    # Verificar Frontend
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null | grep -q "200"; then
        echo -e "  Frontend: ${GREEN}✓ OK${NC}"
    else
        echo -e "  Frontend: ${YELLOW}? UNKNOWN${NC}"
    fi
    
    # Verificar PostgreSQL
    if docker service logs tagfs_database 2>&1 | tail -20 | grep -q "database system is ready"; then
        echo -e "  PostgreSQL: ${GREEN}✓ OK${NC}"
    else
        echo -e "  PostgreSQL: ${YELLOW}? UNKNOWN${NC}"
    fi
    
    echo ""
}

# Función para mostrar comandos útiles
show_commands() {
    echo -e "${CYAN}📌 COMANDOS ÚTILES${NC}"
    echo "────────────────────────────────────────"
    echo "  Escalar backend:     docker service scale tagfs_backend=5"
    echo "  Ver logs completos:  docker service logs -f tagfs_backend"
    echo "  Reiniciar servicio:  docker service update --force tagfs_backend"
    echo "  Inspeccionar:        docker service inspect tagfs_backend"
    echo ""
}

# Main loop
check_swarm

while true; do
    show_header
    show_nodes
    show_services
    show_replicas
    show_stats
    show_health
    show_recent_logs
    show_commands
    
    # Esperar antes de la siguiente actualización
    sleep "$REFRESH_INTERVAL"
done
