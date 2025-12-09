#!/bin/bash
#
# Script para configurar el servidor NFS en el nodo Manager
# Ejecutar con: sudo bash setup-nfs-server.sh
#

set -e

echo "================================================"
echo "  Configuración de Servidor NFS (Manager)"
echo "================================================"
echo ""

# 1. Instalar servidor NFS
echo "[1/5] Instalando nfs-kernel-server..."
apt update
apt install -y nfs-kernel-server

# 2. Crear directorios compartidos
echo "[2/5] Creando directorios compartidos..."
mkdir -p /srv/nfs/tagfs_data
mkdir -p /srv/nfs/postgres_data

# 3. Establecer permisos
echo "[3/5] Configurando permisos..."
chown -R nobody:nogroup /srv/nfs/tagfs_data
chown -R nobody:nogroup /srv/nfs/postgres_data
chmod -R 777 /srv/nfs/tagfs_data
chmod -R 777 /srv/nfs/postgres_data

# 4. Configurar exportaciones NFS
echo "[4/5] Configurando exportaciones NFS..."
# Backup de exports anterior
if [ -f /etc/exports ]; then
    cp /etc/exports /etc/exports.backup.$(date +%Y%m%d_%H%M%S)
fi

# Añadir exportaciones (permitir toda la red local)
cat >> /etc/exports <<EOF

# Tag-Based File System - Directorios compartidos
/srv/nfs/tagfs_data *(rw,sync,no_subtree_check,no_root_squash)
/srv/nfs/postgres_data *(rw,sync,no_subtree_check,no_root_squash)
EOF

# 5. Aplicar configuración y reiniciar servicio
echo "[5/5] Aplicando configuración y reiniciando NFS..."
exportfs -a
systemctl restart nfs-kernel-server
systemctl enable nfs-kernel-server

# Verificar exportaciones
echo ""
echo "✅ Servidor NFS configurado correctamente"
echo ""
echo "Exportaciones activas:"
exportfs -v
echo ""
echo "Directorios compartidos:"
ls -la /srv/nfs/
echo ""
echo "Para montar desde otros nodos, usa:"
echo "  sudo mount <IP_MANAGER>:/srv/nfs/tagfs_data /mnt/tagfs_data"
echo "  sudo mount <IP_MANAGER>:/srv/nfs/postgres_data /mnt/postgres_data"
echo ""
