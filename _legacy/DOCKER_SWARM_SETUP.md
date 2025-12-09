# 📚 Guía Completa: Configuración de Docker Swarm para Tag-based File System

## 🎯 Objetivo
Desplegar una aplicación con **backend en tu VM (manager)** y **frontend en otra PC (worker)**, comunicándose a través de Docker Swarm en una red WiFi local.

---

## 📋 Requisitos Previos

### **Tu máquina (Windows con VirtualBox + Ubuntu VM):**
- ✅ VirtualBox instalado
- ✅ VM Ubuntu con Docker instalado
- ✅ Conectado a WiFi (red `172.20.10.x`)

### **Otra PC (Linux nativo):**
- ✅ Docker instalado
- ✅ Conectado a la misma WiFi

---

## 🔧 Parte 1: Configuración de VirtualBox

### **1.1 Configurar Red en VirtualBox**

Tu VM necesita **dos adaptadores de red**:

**Adaptador 1 (NAT):** Para acceso a Internet
- Settings → Network → Adapter 1
- Attached to: **NAT**
- Advanced → Port Forwarding:
  - **Backend**: Host Port `8000` → Guest Port `8000`
  - **Frontend**: Host Port `80` → Guest Port `80`

**Adaptador 2 (Bridge):** Para comunicación en red local
- Settings → Network → Adapter 2
- ✅ Enable Network Adapter
- Attached to: **Bridged Adapter**
- Name: Selecciona tu adaptador WiFi (NO VPN)
- Mode: Permitir todo

**💡 Importante:** Asegúrate de seleccionar el adaptador WiFi real, no interfaces VPN como WireGuard o Windscribe.

### **1.2 Reiniciar la VM**

Después de configurar los adaptadores, reinicia la VM para que obtenga una IP en la red WiFi.

---

## 🐳 Parte 2: Configuración de Docker en tu VM

### **2.1 Verificar interfaces de red**

```bash
ip addr show
```

**Deberías ver:**
- `enp0s3`: IP NAT (10.0.2.15) - Para Internet
- `enp0s8`: IP WiFi (172.20.10.4) - **Esta es la importante**

### **2.2 Construir las imágenes Docker**

**Backend:**
```bash
cd /home/vboxuser/Tag-based-file-system
sudo docker build -t tagfs-backend:latest -f Dockerfile.backend .
```

**Frontend:**
```bash
cd /home/vboxuser/Tag-based-file-system/frontend-react
sudo docker build --build-arg VITE_API_URL=http://172.20.10.4:8000 -t tagfs-frontend:latest .
```

**💡 Nota:** Reemplaza `172.20.10.4` con la IP real de tu VM (la de `enp0s8`).

---

## 🐝 Parte 3: Inicializar Docker Swarm

### **3.1 Inicializar Swarm en tu VM (Manager)**

```bash
sudo docker swarm init --advertise-addr 172.20.10.4
```

**Esto hará:**
- ✅ Tu VM se convierte en **Swarm Manager**
- ✅ Genera un token para que otros nodos se unan
- ✅ Anuncia el cluster en la IP `172.20.10.4:2377`

**Salida esperada:**
```
Swarm initialized: current node is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join --token SWMTKN-1-xxxxx... 172.20.10.4:2377
```

### **3.2 Obtener el token (si lo necesitas después)**

```bash
sudo docker swarm join-token worker
```

---

## 👥 Parte 4: Unir otra PC al Swarm

### **4.1 En la otra PC (Worker)**

**Primero, verificar conectividad:**
```bash
# Verificar que puede hacer ping a tu VM
ping 172.20.10.4

# Verificar que puede conectarse al puerto de Swarm
nc -zv 172.20.10.4 2377
```

**Si ambos funcionan, unirse al Swarm:**
```bash
sudo docker swarm join --token SWMTKN-1-xxxxx... 172.20.10.4:2377
```

**💡 Importante:** Usa el token que obtuviste en el paso 3.1 o 3.2.

### **4.2 Construir la imagen del frontend en el Worker**

```bash
cd ~/ruta/al/proyecto/frontend-react
sudo docker build --build-arg VITE_API_URL=http://172.20.10.4:8000 -t tagfs-frontend:latest .
```

**🔑 Crucial:** El worker necesita tener la imagen del frontend construida localmente porque Docker Swarm no usa un registry compartido por defecto.

### **4.3 Verificar nodos desde tu VM**

```bash
sudo docker node ls
```

**Deberías ver:**
```
ID                            HOSTNAME      STATUS    AVAILABILITY   MANAGER STATUS
abc123... *                   Ubuntu        Ready     Active         Leader
def456...                     rc46-CX62     Ready     Active
```

---

## 🚀 Parte 5: Desplegar los Servicios

### **5.1 Archivo de configuración (docker-stack-distributed.yml)**

Ya lo tienes creado en `/home/vboxuser/Tag-based-file-system/docker-stack-distributed.yml`:

```yaml
version: '3.8'

services:
  backend:
    image: tagfs-backend:latest
    ports:
      - "8000:8000"
    volumes:
      - tagfs-data:/app/tags_data
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager  # Solo en el manager (tu VM)

  frontend:
    image: tagfs-frontend:latest
    ports:
      - "80:80"
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == worker  # Solo en workers (otra PC)

volumes:
  tagfs-data:
```

### **5.2 Desplegar el stack**

```bash
cd /home/vboxuser/Tag-based-file-system
sudo docker stack deploy -c docker-stack-distributed.yml tagfs
```

---

## 🔍 Parte 6: Verificación

### **6.1 Ver servicios**

```bash
sudo docker service ls
```

**Deberías ver:**
```
ID             NAME             REPLICAS   PORTS
abc123...      tagfs_backend    1/1        *:8000->8000/tcp
def456...      tagfs_frontend   1/1        *:80->80/tcp
```

### **6.2 Ver dónde están corriendo**

```bash
sudo docker service ps tagfs_backend tagfs_frontend
```

**Deberías ver:**
```
NAME               IMAGE                  NODE            STATE
tagfs_backend.1    tagfs-backend:latest   Ubuntu          Running
tagfs_frontend.1   tagfs-frontend:latest  rc46-CX62       Running
```

### **6.3 Ver logs**

```bash
# Logs del backend
sudo docker service logs tagfs_backend

# Logs del frontend
sudo docker service logs tagfs_frontend
```

---

## 🌐 Parte 7: Acceso a la Aplicación

### **7.1 Docker Swarm Routing Mesh**

Docker Swarm publica los puertos en **todos los nodos** del cluster. Esto significa que puedes acceder desde cualquier IP del cluster:

**URLs de acceso:**
```
Frontend: http://172.20.10.4:80  (tu VM)
Frontend: http://172.20.10.3:80  (otra PC)

Backend:  http://172.20.10.4:8000
Backend:  http://172.20.10.3:8000

API Docs: http://172.20.10.4:8000/docs
```

### **7.2 Cómo funciona el Routing Mesh**

```
Usuario → http://172.20.10.4:80
              ↓
    Docker Swarm Routing Mesh (Load Balancer)
              ↓
    Redirige al contenedor (aunque esté en otra PC)
              ↓
    Frontend en rc46-CX62 (172.20.10.3)
```

---

## 🛠️ Comandos Útiles

### **Gestión del Swarm**

```bash
# Ver nodos
sudo docker node ls

# Inspeccionar un nodo
sudo docker node inspect <NODE_ID>

# Promover un worker a manager
sudo docker node promote <NODE_ID>

# Salir del Swarm (worker)
sudo docker swarm leave

# Salir del Swarm (manager - destruye el cluster)
sudo docker swarm leave --force
```

### **Gestión de Servicios**

```bash
# Listar servicios
sudo docker service ls

# Ver detalles de un servicio
sudo docker service ps tagfs_backend

# Ver logs
sudo docker service logs -f tagfs_backend

# Escalar un servicio
sudo docker service scale tagfs_backend=3

# Actualizar un servicio (después de reconstruir imagen)
sudo docker service update --force tagfs_frontend

# Eliminar un servicio
sudo docker service rm tagfs_backend
```

### **Gestión del Stack**

```bash
# Desplegar stack
sudo docker stack deploy -c docker-stack-distributed.yml tagfs

# Listar stacks
sudo docker stack ls

# Ver servicios del stack
sudo docker stack services tagfs

# Ver tareas del stack
sudo docker stack ps tagfs

# Eliminar stack
sudo docker stack rm tagfs
```

---

## 🐛 Troubleshooting

### **Problema: Worker no se puede unir**

```bash
# Verificar conectividad
ping 172.20.10.4
nc -zv 172.20.10.4 2377

# Ver firewall
sudo ufw status

# Permitir puerto 2377
sudo ufw allow 2377/tcp
```

### **Problema: Frontend no corre en el worker**

**Error común:** `mkdir /var/lib/docker: read-only file system`

**Solución:**
```bash
# En el worker
sudo systemctl restart docker
sudo docker run hello-world  # Verificar que Docker funciona

# Salir y volver a unirse al Swarm
sudo docker swarm leave
sudo docker swarm join --token ... 172.20.10.4:2377
```

### **Problema: Frontend no puede conectarse al backend**

**Causa:** URL del backend mal configurada en el frontend.

**Solución:** Reconstruir el frontend con la URL correcta:
```bash
cd frontend-react
sudo docker build --build-arg VITE_API_URL=http://172.20.10.4:8000 -t tagfs-frontend:latest .

# Forzar actualización
sudo docker service update --force tagfs_frontend
```

### **Problema: No aparece la IP de bridge en la VM**

```bash
# Ver todas las interfaces
ip addr show

# Si enp0s8 no tiene IP, obtenerla manualmente
sudo dhclient enp0s8

# O reiniciar la VM
sudo reboot
```

---

## 📊 Arquitectura Final

```
┌─────────────────────────────────────────┐
│         Red WiFi (172.20.10.0/28)       │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────┐  ┌─────────────┐ │
│  │  Windows Host    │  │  PC Worker  │ │
│  │  (172.20.10.2)   │  │(172.20.10.3)│ │
│  │                  │  │             │ │
│  │  ┌────────────┐  │  │  Docker     │ │
│  │  │ VirtualBox │  │  │  Frontend   │ │
│  │  │            │  │  │  Container  │ │
│  │  │  Ubuntu VM │  │  └─────────────┘ │
│  │  │(172.20.10.4)  │                  │
│  │  │            │  │                  │
│  │  │  Docker    │  │                  │
│  │  │  Swarm     │  │                  │
│  │  │  Manager   │  │                  │
│  │  │            │  │                  │
│  │  │  Backend   │  │                  │
│  │  │  Container │  │                  │
│  │  └────────────┘  │                  │
│  └──────────────────┘                  │
│                                         │
│  Routing Mesh: Puertos disponibles     │
│  en todas las IPs del cluster          │
└─────────────────────────────────────────┘
```

---

## ✅ Checklist de Configuración

- [ ] VirtualBox configurado con 2 adaptadores (NAT + Bridge)
- [ ] Port Forwarding configurado (80, 8000, 2377)
- [ ] VM tiene IP en la red WiFi
- [ ] Docker instalado en ambas máquinas
- [ ] Imágenes construidas en ambas máquinas
- [ ] Swarm inicializado en la VM
- [ ] Worker unido al Swarm
- [ ] Stack desplegado
- [ ] Backend corre en manager
- [ ] Frontend corre en worker
- [ ] Aplicación accesible desde el navegador

---

## 📝 Notas Importantes

### **Sobre las IPs:**
- Las IPs específicas (172.20.10.x) son ejemplos de tu red WiFi actual
- Siempre usa la IP de la interfaz bridge (enp0s8) de tu VM
- Verifica las IPs con `ip addr show` antes de configurar

### **Sobre las imágenes Docker:**
- Cada nodo necesita tener construidas localmente las imágenes que va a ejecutar
- Si usas un Docker Registry privado, puedes compartir imágenes automáticamente
- Para producción, considera usar Docker Hub o un registry privado

### **Sobre la seguridad:**
- En producción, usa TLS para comunicación entre nodos
- Configura firewalls apropiadamente
- Usa secrets de Docker Swarm para información sensible

### **Sobre el escalado:**
- Puedes escalar servicios con `docker service scale`
- El Routing Mesh distribuirá la carga automáticamente
- Considera usar límites de recursos en producción

---

## 🚀 Próximos Pasos

Una vez que tengas el sistema funcionando:

1. **Agregar más workers:** Repite el Parte 4 para más PCs
2. **Configurar volúmenes persistentes:** Usa NFS o volúmenes compartidos
3. **Implementar CI/CD:** Automatiza el despliegue
4. **Monitoreo:** Configura Prometheus + Grafana para monitorear el cluster
5. **Backups:** Implementa estrategia de respaldo para datos

---

**¡Con esto tienes una guía completa para replicar toda la configuración desde cero!** 🚀

**Última actualización:** Octubre 2025
