# 🔄 Configuración de Docker Swarm Multi-Manager

## 🎯 Objetivo
Configurar un cluster Docker Swarm con **dos managers** donde ambas PCs puedan:
- ✅ Gestionar servicios independientemente
- ✅ Levantar y desmontar sus propios contenedores
- ✅ Tener alta disponibilidad (si un manager falla, el otro continúa)

---

## 📊 Arquitectura

```
┌─────────────────────────────────────────────────┐
│         Docker Swarm Multi-Manager              │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────┐      ┌─────────────────┐ │
│  │  VM Ubuntu       │      │  PC Linux       │ │
│  │  (172.20.10.4)   │◄────►│  (172.20.10.3)  │ │
│  │                  │      │                 │ │
│  │  Manager 1       │      │  Manager 2      │ │
│  │  (Leader/Follower)│     │  (Leader/Follower)│
│  │                  │      │                 │ │
│  │  Backend Service │      │  Frontend Service│
│  └──────────────────┘      └─────────────────┘ │
│                                                 │
│  Raft Consensus: Mantiene estado sincronizado  │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Paso a Paso

### **Paso 1: Estado Actual del Swarm**

Primero verifica el estado actual:

**En tu VM (Manager actual):**
```bash
sudo docker node ls
```

Deberías ver algo como:
```
ID                            HOSTNAME      STATUS    AVAILABILITY   MANAGER STATUS
abc123... *                   Ubuntu        Ready     Active         Leader
def456...                     rc46-CX62     Ready     Active         
```

---

### **Paso 2: Promover al Worker a Manager**

**En tu VM:**
```bash
# Obtener el ID del nodo del otro PC
sudo docker node ls

# Promover a manager (reemplaza NODE_ID con el ID real)
sudo docker node promote <NODE_ID_DE_RC46>

# Verificar
sudo docker node ls
```

**Ahora deberías ver:**
```
ID                            HOSTNAME      STATUS    AVAILABILITY   MANAGER STATUS
abc123... *                   Ubuntu        Ready     Active         Leader
def456...                     rc46-CX62     Ready     Active         Reachable
```

**💡 Significado:**
- **Leader**: Manager principal que toma decisiones
- **Reachable**: Manager secundario que puede convertirse en Leader si el primero falla

---

### **Paso 3: Verificar desde ambas PCs**

**Ahora él puede ejecutar en su PC:**
```bash
sudo docker node ls
```

Debería ver la misma lista de nodos. ¡Ambos tienen control total del cluster!

---

### **Paso 4: Crear Red Overlay Compartida**

Antes de desplegar servicios, creen la red overlay que ambos usarán:

**Ejecuta en TU VM (solo una vez):**
```bash
sudo docker network create --driver overlay --attachable tagfs-overlay
```

**Verificar desde ambas PCs:**
```bash
sudo docker network ls | grep tagfs
```

---

### **Paso 5: Actualizar archivos de configuración**

Ahora vamos a actualizar los archivos para que cada manager pueda correr su servicio en su propio nodo.

---

## 📁 Configuración de Servicios

### **A. Backend (Tu VM)**

**Archivo: `docker-service-backend.yml`**

```yaml
version: '3.8'

services:
  backend:
    image: tagfs-backend:latest
    ports:
      - "8000:8000"
    volumes:
      - tagfs-data:/app/tags_data
    environment:
      - PYTHONUNBUFFERED=1
    networks:
      - tagfs-overlay
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == Ubuntu  # Específico para tu VM
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

networks:
  tagfs-overlay:
    external: true

volumes:
  tagfs-data:
    driver: local
```

---

### **B. Frontend (Su PC)**

**Archivo: `docker-service-frontend.yml`**

```yaml
version: '3.8'

services:
  frontend:
    image: tagfs-frontend:latest
    ports:
      - "80:80"
    networks:
      - tagfs-overlay
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.hostname == rc46-CX62-6QD  # Específico para su PC
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '0.25'
          memory: 256M

networks:
  tagfs-overlay:
    external: true
```

---

## 🎮 Gestión de Servicios

### **Tú: Levantar Backend**

**En tu VM:**
```bash
cd /home/vboxuser/Tag-based-file-system

# Levantar backend
sudo docker stack deploy -c docker-service-backend.yml backend

# Verificar
sudo docker service ls
sudo docker service ps backend_backend
```

### **Él: Levantar Frontend**

**En su PC:**
```bash
cd ~/ruta/al/proyecto

# Levantar frontend
sudo docker stack deploy -c docker-service-frontend.yml frontend

# Verificar
sudo docker service ls
sudo docker service ps frontend_frontend
```

---

## 🛠️ Comandos de Gestión Individual

### **Tú: Gestionar Backend**

```bash
# Ver estado
sudo docker service ls
sudo docker service ps backend_backend

# Ver logs
sudo docker service logs -f backend_backend

# Escalar (más réplicas)
sudo docker service scale backend_backend=2

# Actualizar (después de reconstruir imagen)
sudo docker service update --force backend_backend

# Detener (0 réplicas)
sudo docker service scale backend_backend=0

# Reiniciar (1 réplica)
sudo docker service scale backend_backend=1

# Eliminar completamente
sudo docker stack rm backend
```

### **Él: Gestionar Frontend**

```bash
# Ver estado
sudo docker service ls
sudo docker service ps frontend_frontend

# Ver logs
sudo docker service logs -f frontend_frontend

# Escalar
sudo docker service scale frontend_frontend=2

# Actualizar
sudo docker service update --force frontend_frontend

# Detener
sudo docker service scale frontend_frontend=0

# Reiniciar
sudo docker service scale frontend_frontend=1

# Eliminar
sudo docker stack rm frontend
```

---

## 📊 Verificación desde Ambas PCs

**Ambos pueden ejecutar:**

```bash
# Ver todos los servicios del cluster
sudo docker service ls

# Ver todos los nodos
sudo docker node ls

# Ver tareas de todos los servicios
sudo docker stack ps backend
sudo docker stack ps frontend

# Ver todas las redes
sudo docker network ls
```

---

## 🔄 Flujo de Trabajo Típico

### **Escenario 1: Iniciar todo desde cero**

**1. Tú levantas el backend:**
```bash
sudo docker stack deploy -c docker-service-backend.yml backend
```

**2. Él levanta el frontend:**
```bash
sudo docker stack deploy -c docker-service-frontend.yml frontend
```

**3. Ambos verifican:**
```bash
sudo docker service ls
```

Deberían ver:
```
ID        NAME                MODE        REPLICAS   PORTS
abc123    backend_backend     replicated  1/1        *:8000->8000/tcp
def456    frontend_frontend   replicated  1/1        *:80->80/tcp
```

---

### **Escenario 2: Tú actualizas el backend**

**1. Reconstruir imagen:**
```bash
cd /home/vboxuser/Tag-based-file-system
sudo docker build -t tagfs-backend:latest -f Dockerfile.backend .
```

**2. Actualizar servicio:**
```bash
sudo docker service update --force backend_backend
```

**3. Él puede ver el progreso:**
```bash
sudo docker service ps backend_backend
```

---

### **Escenario 3: Él detiene el frontend temporalmente**

**En su PC:**
```bash
# Detener (mantiene el servicio, 0 réplicas)
sudo docker service scale frontend_frontend=0

# Verificar
sudo docker service ls
# Mostrará: frontend_frontend  replicated  0/0

# Reiniciar cuando quiera
sudo docker service scale frontend_frontend=1
```

---

### **Escenario 4: Él actualiza el frontend**

**1. Reconstruir imagen:**
```bash
cd ~/proyecto/frontend-react
sudo docker build --build-arg VITE_API_URL=http://172.20.10.4:8000 -t tagfs-frontend:latest .
```

**2. Actualizar servicio:**
```bash
sudo docker service update --force frontend_frontend
```

**3. Tú puedes ver el progreso:**
```bash
sudo docker service ps frontend_frontend
```

---

## ⚠️ Consideraciones Importantes

### **1. Alta Disponibilidad**
- Con 2 managers, el cluster tolera la pérdida de **0 managers** para escrituras
- Si un manager falla, el cluster sigue **leyendo** pero no se pueden hacer cambios
- Para verdadera HA, necesitas **3 o 5 managers** (siempre número impar)

### **2. Consenso Raft**
- Los managers usan el algoritmo Raft para mantener consistencia
- Las decisiones se toman por mayoría
- Con 2 managers, necesitas que **ambos estén online** para modificar el cluster

### **3. Imágenes Docker**
- Cada nodo necesita tener las imágenes construidas localmente
- O pueden usar un Docker Registry compartido (Docker Hub o privado)

### **4. Volúmenes de Datos**
- El backend usa un volumen local (`tagfs-data`)
- Si el backend se mueve a otro nodo, los datos no se moverán
- Para datos compartidos, considera NFS o volúmenes distribuidos

---

## 🔐 Seguridad y Mejores Prácticas

### **1. Comunicación Segura**
```bash
# Los managers se comunican por el puerto 2377 (TLS automático)
# Los workers se comunican por el puerto 7946 (gossip protocol)
# Los contenedores usan overlay por el puerto 4789 (VXLAN)
```

### **2. Firewall**
```bash
# Abrir puertos necesarios en ambas PCs
sudo ufw allow 2377/tcp    # Swarm management
sudo ufw allow 7946/tcp    # Node communication
sudo ufw allow 7946/udp    # Node communication
sudo ufw allow 4789/udp    # Overlay network
```

### **3. Backups**
```bash
# Hacer backup de la configuración del Swarm (solo managers)
sudo tar czf swarm-backup.tar.gz /var/lib/docker/swarm
```

---

## 🐛 Troubleshooting

### **Problema: Un manager no puede ver cambios**

```bash
# Verificar conectividad entre managers
ping 172.20.10.4  # Desde su PC a tu VM
ping 172.20.10.3  # Desde tu VM a su PC

# Verificar estado del Swarm
sudo docker info | grep -A 5 Swarm

# Verificar logs de Docker
sudo journalctl -u docker -n 50
```

### **Problema: "context deadline exceeded"**

```bash
# Reiniciar Docker en ambas máquinas
sudo systemctl restart docker

# Si persiste, salir y volver a crear el Swarm
sudo docker swarm leave --force
sudo docker swarm init --advertise-addr 172.20.10.4
```

### **Problema: Servicios no se comunican**

```bash
# Verificar que la red overlay existe
sudo docker network ls | grep tagfs

# Si no existe, crearla
sudo docker network create --driver overlay --attachable tagfs-overlay

# Verificar que los servicios usan la misma red
sudo docker service inspect backend_backend --format '{{.Spec.TaskTemplate.Networks}}'
sudo docker service inspect frontend_frontend --format '{{.Spec.TaskTemplate.Networks}}'
```

---

## 📚 Comandos de Referencia Rápida

### **Ver Estado del Cluster**
```bash
sudo docker node ls                  # Listar nodos
sudo docker service ls               # Listar servicios
sudo docker stack ls                 # Listar stacks
sudo docker network ls               # Listar redes
```

### **Gestión de Nodos**
```bash
sudo docker node inspect <NODE>      # Detalles de un nodo
sudo docker node update <NODE>       # Actualizar nodo
sudo docker node promote <NODE>      # Promover a manager
sudo docker node demote <NODE>       # Degradar a worker
```

### **Gestión de Servicios**
```bash
sudo docker service create           # Crear servicio
sudo docker service update           # Actualizar servicio
sudo docker service scale            # Escalar servicio
sudo docker service rm               # Eliminar servicio
sudo docker service logs             # Ver logs
```

### **Información del Sistema**
```bash
sudo docker info                     # Info de Docker
sudo docker system df                # Uso de disco
sudo docker system prune             # Limpiar recursos no usados
```

---

## ✅ Checklist de Verificación

- [ ] Ambos nodos son managers
- [ ] Ambos pueden ejecutar `docker node ls` exitosamente
- [ ] Red overlay `tagfs-overlay` existe
- [ ] Backend desplegado en tu nodo
- [ ] Frontend desplegado en su nodo
- [ ] Servicios pueden verse desde ambas PCs
- [ ] Aplicación accesible desde cualquier IP del cluster
- [ ] Ambos pueden gestionar sus servicios independientemente

---

## 🎯 Resumen

Con esta configuración:
- ✅ **Tú controlas**: Backend (puede iniciarlo, detenerlo, actualizarlo)
- ✅ **Él controla**: Frontend (puede iniciarlo, detenerlo, actualizarlo)
- ✅ **Ambos pueden ver**: Estado completo del cluster
- ✅ **Alta disponibilidad**: Si un manager falla temporalmente, el otro mantiene el cluster
- ✅ **Routing Mesh**: Los servicios son accesibles desde cualquier IP del cluster

**¡Ahora tienen un cluster verdaderamente distribuido y colaborativo!** 🚀

---

**Última actualización:** Octubre 2025
