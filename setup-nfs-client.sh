#!/bin/bash
#
# Script para configurar cliente NFS en nodos Worker
# Ejecutar con: sudo bash setup-nfs-client.sh <IP_MANAGER>
#
# Ejemplo: sudo bash setup-nfs-client.sh 172.20.10.4
#

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Debes proporcionar la IP del servidor NFS (Manager)"
    echo "Uso: sudo bash setup-nfs-client.sh <IP_MANAGER>"
    echo "Ejemplo: sudo bash setup-nfs-client.sh 172.20.10.4"
    exit 1
fi

NFS_SERVER_IP="$1"

echo "================================================"
echo "  Configuración de Cliente NFS (Worker)"
echo "  Servidor NFS: $NFS_SERVER_IP"
echo "================================================"
echo ""

# 1. Instalar cliente NFS
echo "[1/4] Instalando nfs-common..."
apt update
apt install -y nfs-common

# 2. Crear puntos de montaje
echo "[2/4] Creando puntos de montaje..."
mkdir -p /mnt/tagfs_data
mkdir -p /mnt/postgres_data

# 3. Probar montaje manual
echo "[3/4] Probando conexión con servidor NFS..."
if mount -t nfs4 "${NFS_SERVER_IP}:/srv/nfs/tagfs_data" /mnt/tagfs_data; then
    echo "✅ Montaje de tagfs_data exitoso"
    umount /mnt/tagfs_data
else
    echo "❌ Error al montar tagfs_data desde ${NFS_SERVER_IP}"
    exit 1
fi

if mount -t nfs4 "${NFS_SERVER_IP}:/srv/nfs/postgres_data" /mnt/postgres_data; then
    echo "✅ Montaje de postgres_data exitoso"
    umount /mnt/postgres_data
else
    echo "❌ Error al montar postgres_data desde ${NFS_SERVER_IP}"
    exit 1
fi

# 4. Configurar montaje automático en /etc/fstab
echo "[4/4] Configurando montaje automático en /etc/fstab..."
# Backup de fstab
cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)

# Añadir entradas si no existen
if ! grep -q "/srv/nfs/tagfs_data" /etc/fstab; then
    echo "${NFS_SERVER_IP}:/srv/nfs/tagfs_data /mnt/tagfs_data nfs defaults 0 0" >> /etc/fstab
fi

if ! grep -q "/srv/nfs/postgres_data" /etc/fstab; then
    echo "${NFS_SERVER_IP}:/srv/nfs/postgres_data /mnt/postgres_data nfs defaults 0 0" >> /etc/fstab
fi

# Montar todo desde fstab
mount -a

echo ""
echo "✅ Cliente NFS configurado correctamente"
echo ""
echo "Puntos de montaje activos:"
df -h | grep nfs || true
echo ""
echo "Contenido de /mnt/tagfs_data:"
ls -la /mnt/tagfs_data || echo "(vacío)"
echo ""
