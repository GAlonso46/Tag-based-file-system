# 🔧 Guía de Troubleshooting y Recovery

## 📋 Índice Rápido

1. [Problemas de Despliegue](#problemas-de-despliegue)
2. [Errores de PostgreSQL](#errores-de-postgresql)
3. [Problemas de NFS](#problemas-de-nfs)
4. [Servicios No Arrancan](#servicios-no-arrancan)
5. [Problemas de Red](#problemas-de-red)
6. [Performance Degradado](#performance-degradado)
7. [Recuperación ante Fallos](#recuperación-ante-fallos)

---

## 🚨 Problemas de Despliegue

### Síntoma: `deploy.sh` falla con "permission denied"

**Causa:** No se está ejecutando con sudo

**Solución:**
```bash
sudo bash deploy.sh manager <IP> <PASSWORD>
```

### Síntoma: "Docker daemon not running"

**Causa:** Docker no está instalado o no está activo

**Solución:**
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Iniciar Docker
sudo systemctl start docker
sudo systemctl enable docker

# Agregar usuario a grupo docker (opcional)
sudo usermod -aG docker $USER
```

### Síntoma: "NFS mount failed"

**Causa:** NFS no está configurado correctamente

**Solución:**
```bash
# En Manager
sudo systemctl status nfs-kernel-server
sudo exportfs -v

# Verificar firewall
sudo ufw allow from 192.168.0.0/16 to any port nfs

# En Worker
sudo systemctl status nfs-common
sudo mount -v -t nfs4 <IP>:/srv/nfs/tagfs_data /mnt/test
```

---

## 🐘 Errores de PostgreSQL

### Síntoma: "database system is not ready"

**Causa:** PostgreSQL todavía está iniciando

**Solución:**
```bash
# Esperar a que esté listo (30-60 segundos)
docker service logs -f tagfs_database

# Cuando veas "database system is ready to accept connections", continúa
```

### Síntoma: "could not connect to server"

**Causa:** PostgreSQL no está corriendo o no es accesible

**Diagnóstico:**
```bash
# Ver estado del servicio
docker service ps tagfs_database

# Ver logs
docker service logs --tail 50 tagfs_database

# Verificar que el contenedor existe
docker ps | grep postgres
```

**Solución:**
```bash
# Opción 1: Reiniciar servicio
docker service update --force tagfs_database

# Opción 2: Recrear servicio
docker service rm tagfs_database
docker stack deploy -c docker-stack-distributed.yml tagfs

# Opción 3: Verificar volumen NFS
ls -la /srv/nfs/postgres_data
sudo chown -R 999:999 /srv/nfs/postgres_data  # UID de postgres
```

### Síntoma: "relation does not exist"

**Causa:** Tablas no han sido creadas

**Solución:**
```bash
# Ejecutar migración
export DATABASE_URL="postgresql://tagfs_user:PASSWORD@localhost:5432/tagfs"
python3 migrate_sqlite_to_postgres.py
```

### Síntoma: "too many connections"

**Causa:** Pool de conexiones agotado

**Solución:**
```bash
# Escalar down y up el backend
docker service scale tagfs_backend=0
sleep 5
docker service scale tagfs_backend=3

# O modificar pool_size en api/database.py
```

---

## 📂 Problemas de NFS

### Síntoma: "Stale file handle"

**Causa:** Servidor NFS reinició, handles antiguos inválidos

**Solución:**
```bash
# En Workers
sudo umount -f /mnt/tagfs_data
sudo mount -a

# Si falla
sudo systemctl restart nfs-common
sudo mount <IP>:/srv/nfs/tagfs_data /mnt/tagfs_data
```

### Síntoma: "Permission denied" en archivos

**Causa:** Permisos incorrectos en NFS

**Solución:**
```bash
# En Manager
sudo chmod -R 777 /srv/nfs/tagfs_data
sudo chown -R nobody:nogroup /srv/nfs/tagfs_data

# Verificar exports
sudo exportfs -v
# Debe mostrar: rw,sync,no_root_squash,no_subtree_check

# Reexportar
sudo exportfs -ra
```

### Síntoma: Archivos no se sincronizan entre nodos

**Causa:** NFS cache desactualizado

**Solución:**
```bash
# Forzar sync en Manager
sudo exportfs -f

# En Workers, remontar con opciones específicas
sudo mount -o remount,noac <IP>:/srv/nfs/tagfs_data /mnt/tagfs_data
```

### Síntoma: Performance muy lento

**Causa:** Opciones de montaje no óptimas

**Solución:**
```bash
# Editar /etc/fstab con opciones optimizadas
<IP>:/srv/nfs/tagfs_data /mnt/tagfs_data nfs4 rw,hard,intr,timeo=600,retrans=2 0 0

# Remontar
sudo umount /mnt/tagfs_data
sudo mount /mnt/tagfs_data
```

---

## 🐳 Servicios No Arrancan

### Síntoma: Servicio en estado "Pending"

**Diagnóstico:**
```bash
docker service ps tagfs_backend --no-trunc
```

**Causas comunes:**

#### 1. Imagen no encontrada
```bash
# Verificar imágenes
docker images | grep tagfs

# Rebuild si es necesario
docker build -t tagfs-backend:latest -f Dockerfile.backend .
```

#### 2. Volumen no disponible
```bash
# Verificar que NFS está montado
mount | grep nfs

# Verificar que el volumen existe en Docker
docker volume ls | grep tagfs
```

#### 3. Constraints no se cumplen
```bash
# Ver placement constraints
docker service inspect tagfs_backend | grep -A 10 Placement

# Ver labels de nodos
docker node ls -q | xargs docker node inspect | grep -E "Hostname|Labels"
```

### Síntoma: Servicio se reinicia constantemente

**Diagnóstico:**
```bash
# Ver logs con timestamps
docker service logs --timestamps --tail 100 tagfs_backend

# Ver eventos del servicio
docker service ps tagfs_backend
```

**Soluciones:**

#### Error en la aplicación
```bash
# Probar la imagen localmente
docker run -it --rm tagfs-backend:latest bash
# Dentro del container:
python3 -c "from api.main import app; print('OK')"
```

#### Falta variable de entorno
```bash
# Verificar variables
docker service inspect tagfs_backend | grep -A 20 Env

# Actualizar variable
docker service update --env-add DATABASE_URL="postgresql://..." tagfs_backend
```

#### Health check falla
```bash
# Verificar health check
docker service inspect tagfs_backend | grep -A 10 HealthCheck

# Desactivar temporalmente
docker service update --health-cmd "exit 0" tagfs_backend
```

---

## 🌐 Problemas de Red

### Síntoma: Workers no pueden unirse al Swarm

**Diagnóstico:**
```bash
# En Manager, verificar puertos
sudo netstat -tlnp | grep -E "2377|7946|4789"

# Verificar firewall
sudo ufw status
```

**Solución:**
```bash
# Abrir puertos necesarios
sudo ufw allow 2377/tcp   # Cluster management
sudo ufw allow 7946/tcp   # Node communication
sudo ufw allow 7946/udp
sudo ufw allow 4789/udp   # Overlay network

# Regenerar token
docker swarm join-token worker
```

### Síntoma: Servicios no se comunican entre sí

**Diagnóstico:**
```bash
# Verificar red overlay
docker network ls | grep ingress

# Inspeccionar red
docker network inspect ingress
```

**Solución:**
```bash
# Recrear red overlay
docker network rm ingress
docker swarm init --force-new-cluster

# Redesplegar stack
docker stack deploy -c docker-stack-distributed.yml tagfs
```

### Síntoma: No se puede acceder a servicios desde fuera

**Diagnóstico:**
```bash
# Verificar que el puerto está publicado
docker service inspect tagfs_backend | grep PublishedPort

# Verificar que hay réplicas corriendo
docker service ps tagfs_backend
```

**Solución:**
```bash
# Verificar firewall
sudo ufw allow 8000/tcp
sudo ufw allow 3000/tcp

# Verificar que el servicio escucha en 0.0.0.0
docker service logs tagfs_backend | grep "Uvicorn running"
```

---

## 📉 Performance Degradado

### Síntoma: Respuestas lentas (> 1s)

**Diagnóstico:**
```bash
# Monitoreo en tiempo real
bash monitor.sh

# Ver uso de CPU/RAM
docker stats

# Ver logs para errores
docker service logs --tail 100 tagfs_backend | grep -i error
```

**Soluciones:**

#### 1. Escalar backend
```bash
docker service scale tagfs_backend=5
```

#### 2. Optimizar PostgreSQL
```bash
# Ejecutar optimización
export DATABASE_URL="postgresql://user:pass@localhost:5432/tagfs"
python3 optimize_postgres.py

# Verificar índices
docker exec -it $(docker ps -q -f name=tagfs_database) \
  psql -U tagfs_user -d tagfs -c "\di"
```

#### 3. Verificar NFS
```bash
# Stats de NFS
nfsstat -c  # En workers
nfsstat -s  # En manager

# Si hay muchos retries, ajustar timeout
sudo mount -o remount,timeo=600 /mnt/tagfs_data
```

#### 4. Limpiar Docker
```bash
# Limpiar containers parados
docker container prune -f

# Limpiar imágenes no usadas
docker image prune -a -f

# Limpiar volúmenes huérfanos
docker volume prune -f
```

### Síntoma: Muchos errores 500

**Diagnóstico:**
```bash
# Ver stack trace en logs
docker service logs --tail 200 tagfs_backend | grep -A 10 "ERROR"

# Verificar conexión a BD
docker service logs tagfs_database | tail -50
```

**Solución:**
```bash
# Reiniciar servicios en orden
docker service update --force tagfs_database
sleep 30
docker service update --force tagfs_backend
sleep 10
docker service update --force tagfs_frontend
```

---

## 🚑 Recuperación ante Fallos

### Escenario 1: Nodo Manager cae

**Síntomas:**
- No se pueden crear nuevos servicios
- Workers quedan huérfanos

**Recovery:**
```bash
# Si hay múltiples managers (recomendado)
# Los otros managers toman control automáticamente

# Si solo hay 1 manager, recuperar:
# 1. Reiniciar nodo manager
sudo reboot

# 2. Esperar a que Docker Swarm arranque
docker node ls

# 3. Si Swarm no arranca, forzar recovery
docker swarm init --force-new-cluster --advertise-addr <IP>

# 4. Volver a unir workers
# En cada worker:
docker swarm leave
docker swarm join --token <NEW_TOKEN> <IP>:2377
```

### Escenario 2: Worker cae

**Síntomas:**
- Servicios redistribuidos automáticamente
- Algunas réplicas en "Shutdown"

**Recovery:**
```bash
# Docker Swarm automáticamente redistribuye réplicas
# Verificar redistribución
docker service ps tagfs_backend

# Si el worker vuelve, se reintegra automáticamente
# En el worker recuperado:
docker node ls  # Debe aparecer como Ready
```

### Escenario 3: PostgreSQL corrupto

**Síntomas:**
- "database corruption detected"
- Servicios fallan al conectar

**Recovery:**
```bash
# 1. Parar servicios que usan BD
docker service scale tagfs_backend=0
docker service scale tagfs_frontend=0

# 2. Backup del volumen
sudo tar -czf /backup/postgres_$(date +%F).tar.gz /srv/nfs/postgres_data

# 3. Eliminar servicio de BD
docker service rm tagfs_database

# 4. Limpiar volumen corrupto
sudo rm -rf /srv/nfs/postgres_data/*

# 5. Redesplegar BD
docker stack deploy -c docker-stack-distributed.yml tagfs

# 6. Esperar a que PostgreSQL esté listo
docker service logs -f tagfs_database

# 7. Restaurar datos desde backup o migración
export DATABASE_URL="postgresql://user:pass@localhost:5432/tagfs"
python3 migrate_sqlite_to_postgres.py

# 8. Reescalar servicios
docker service scale tagfs_backend=3
docker service scale tagfs_frontend=2
```

### Escenario 4: NFS Server cae

**Síntomas:**
- "Stale file handle"
- Todos los servicios fallan

**Recovery:**
```bash
# 1. Reiniciar servidor NFS
sudo systemctl restart nfs-kernel-server

# 2. Verificar exports
sudo exportfs -v

# 3. Reexportar
sudo exportfs -ra

# 4. En todos los workers, remontar
sudo umount -f /mnt/tagfs_data
sudo mount -a

# 5. Reiniciar servicios
docker service update --force tagfs_backend
docker service update --force tagfs_frontend
docker service update --force tagfs_database
```

### Escenario 5: Stack completo no responde

**Recovery Nuclear:**
```bash
# 1. Eliminar stack completo
docker stack rm tagfs

# 2. Esperar a que se limpien recursos (1-2 min)
watch docker ps

# 3. Limpiar volúmenes si es necesario
docker volume prune -f

# 4. Redesplegar desde cero
export NFS_SERVER_IP=<IP>
export DB_PASSWORD=<PASSWORD>
docker stack deploy -c docker-stack-distributed.yml tagfs

# 5. Ejecutar migración
sleep 60  # Esperar PostgreSQL
python3 migrate_sqlite_to_postgres.py
python3 optimize_postgres.py

# 6. Verificar
bash test_distributed.sh <IP>
```

---

## 🔍 Comandos de Diagnóstico Útiles

```bash
# Ver todo el estado del cluster
docker node ls
docker service ls
docker network ls
docker volume ls

# Logs completos de un servicio
docker service logs --tail 500 --follow tagfs_backend

# Inspeccionar servicio
docker service inspect tagfs_backend --pretty

# Ver eventos del sistema
docker events --filter type=service

# Recursos de todos los containers
docker stats --no-stream

# Verificar overlay network
docker network inspect ingress

# Ver placement de réplicas
docker service ps tagfs_backend --format "{{.Node}}: {{.CurrentState}}"

# Ejecutar comando en container
docker exec -it $(docker ps -q -f name=tagfs_backend | head -1) bash

# Ver variables de entorno
docker service inspect tagfs_backend | grep -A 30 Env

# Test de conectividad entre servicios
docker run --rm --network tagfs_default alpine ping -c 3 database
```

---

## 📞 Checklist Rápido de Troubleshooting

Cuando algo falla, sigue esta secuencia:

1. ✅ **Verificar servicios**
   ```bash
   docker service ls
   docker service ps <service_name>
   ```

2. ✅ **Ver logs**
   ```bash
   docker service logs --tail 100 <service_name>
   ```

3. ✅ **Verificar NFS**
   ```bash
   mount | grep nfs
   ls -la /srv/nfs/tagfs_data
   ```

4. ✅ **Verificar PostgreSQL**
   ```bash
   docker service logs tagfs_database | tail -20
   ```

5. ✅ **Verificar red**
   ```bash
   docker network ls
   ping -c 3 <manager_ip>
   ```

6. ✅ **Reintentar con fuerza**
   ```bash
   docker service update --force <service_name>
   ```

7. ✅ **Recovery completo**
   ```bash
   docker stack rm tagfs
   docker stack deploy -c docker-stack-distributed.yml tagfs
   ```

---

## 📚 Referencias

- Logs: `docker service logs -f tagfs_backend`
- Monitor: `bash monitor.sh`
- Tests: `bash test_distributed.sh <IP>`
- Stress: `bash stress_test.sh <IP> <clients>`

---

**💡 Tip:** Guarda este documento y tenlo a mano durante el despliegue y operación del sistema.

