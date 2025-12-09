# 🏗️ ARQUITECTURA DEL SISTEMA - Análisis Detallado

## 📐 ARQUITECTURA ACTUAL (Con Problemas)

```
┌─────────────────────────────────────────────────────────────────┐
│                         RED WiFi Local                          │
│                        (172.20.10.0/24)                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│  NODO 1 (Manager)         │   │  NODO 2 (Worker)          │
│  IP: 172.20.10.4          │   │  IP: 172.20.10.3          │
├───────────────────────────┤   ├───────────────────────────┤
│                           │   │                           │
│  ┌─────────────────────┐  │   │  ┌─────────────────────┐  │
│  │  Backend (x2)       │  │   │  │  Frontend (x1)      │  │
│  │  ┌──────────────┐   │  │   │  │  - React App        │  │
│  │  │ FastAPI      │   │  │   │  │  - Nginx            │  │
│  │  │ Port: 8000   │   │  │   │  │  - Port: 80         │  │
│  │  └──────────────┘   │  │   │  └─────────────────────┘  │
│  └─────────────────────┘  │   │                           │
│           │               │   │                           │
│           ▼               │   │                           │
│  ┌─────────────────────┐  │   │                           │
│  │  SQLite Database    │  │   │  ❌ NO ACCESO A BD       │
│  │  users.db           │  │   │                           │
│  │  📍 LOCAL ONLY      │◄─┼───┼──❌ NO COMPARTIDA        │
│  └─────────────────────┘  │   │                           │
│           │               │   │                           │
│           ▼               │   │                           │
│  ┌─────────────────────┐  │   │                           │
│  │  Archivos           │  │   │                           │
│  │  /tags_data/files/  │  │   │  ❌ NO ACCESO A ARCHIVOS │
│  │  files.json         │  │   │                           │
│  │  📍 LOCAL ONLY      │◄─┼───┼──❌ NO COMPARTIDOS       │
│  └─────────────────────┘  │   │                           │
│                           │   │                           │
└───────────────────────────┘   └───────────────────────────┘

🔴 PROBLEMAS CRÍTICOS:
1. SQLite solo accesible desde Nodo 1
2. Archivos solo accesibles desde Nodo 1
3. Si Nodo 1 falla → TODO el sistema falla
4. Backend en Nodo 2 no puede acceder a datos
5. No hay redundancia de datos
```

---

## 🎯 ARQUITECTURA OBJETIVO (Distribuida y Robusta)

```
┌─────────────────────────────────────────────────────────────────┐
│                         RED WiFi Local                          │
│                        (172.20.10.0/24)                         │
│                   Docker Swarm Routing Mesh                     │
│              (Balanceo de carga automático)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│  NODO 1 (Manager)         │   │  NODO 2 (Worker)          │
│  IP: 172.20.10.4          │   │  IP: 172.20.10.3          │
├───────────────────────────┤   ├───────────────────────────┤
│                           │   │                           │
│  ┌─────────────────────┐  │   │  ┌─────────────────────┐  │
│  │  Backend (x2)       │  │   │  │  Backend (x2)       │  │
│  │  - FastAPI          │  │   │  │  - FastAPI          │  │
│  │  - Auth JWT         │  │   │  │  - Auth JWT         │  │
│  │  - Port: 8000       │  │   │  │  - Port: 8000       │  │
│  └──────────┬──────────┘  │   │  └──────────┬──────────┘  │
│             │             │   │             │             │
│  ┌─────────────────────┐  │   │  ┌─────────────────────┐  │
│  │  Frontend (x2)      │  │   │  │  Frontend (x2)      │  │
│  │  - React            │  │   │  │  - React            │  │
│  │  - Port: 80         │  │   │  │  - Port: 80         │  │
│  └──────────┬──────────┘  │   │  └──────────┬──────────┘  │
│             │             │   │             │             │
│             └─────────────┼───┼─────────────┘             │
│                     │     │   │     │                     │
│                     ▼     │   │     ▼                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         PostgreSQL Database (Servicio)              │  │
│  │         - Port: 5432                                │  │
│  │         - Usuarios, Metadata, Sesiones              │  │
│  │         ✅ Accesible desde TODOS los nodos          │  │
│  └────────────────────┬────────────────────────────────┘  │
│                       │                                   │
│                       ▼                                   │
│              ┌──────────────────┐                         │
│              │  Volumen NFS/    │                         │
│              │  GlusterFS       │                         │
│              │  (Postgres Data) │                         │
│              └──────────────────┘                         │
│                                                            │
├────────────────────────────────┬───────────────────────────┤
│                                │                           │
│                                ▼                           │
│     ┌──────────────────────────────────────────────┐      │
│     │   ALMACENAMIENTO COMPARTIDO (NFS/GlusterFS)  │      │
│     │   /srv/nfs/tagfs_data                        │      │
│     │   ┌────────────────────────────────────────┐ │      │
│     │   │  files.json (Metadata de tags)         │ │      │
│     │   │  files/ (Archivos binarios)            │ │      │
│     │   │  ✅ Montado en TODOS los nodos         │ │      │
│     │   └────────────────────────────────────────┘ │      │
│     └──────────────────┬───────────────────────────┘      │
│                        │                                   │
└────────────────────────┼───────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│  Replica 1       │           │  Replica 2       │
│  (NFS Server)    │◄─────────►│  (GlusterFS)     │
│  Nodo Manager    │  Sync     │  Opcional        │
└──────────────────┘           └──────────────────┘

✅ SOLUCIONES IMPLEMENTADAS:
1. PostgreSQL accesible desde todos los nodos
2. NFS/GlusterFS compartido entre todos los nodos
3. Múltiples réplicas de Backend y Frontend
4. Balanceo de carga automático (Swarm Routing Mesh)
5. Si un nodo falla, el otro continúa funcionando
6. Datos replicados (no se pierden)
```

---

## 🔄 FLUJO DE DATOS - Upload de Archivo

### ANTES (Problemático)
```
Usuario
  │
  ▼
Frontend (Nodo 2)
  │ POST /files
  ▼
Routing Mesh → Backend (Nodo 1) ✅ OK
  │
  ├─► Guardar archivo en /tags_data/files/ (Local Nodo 1) ✅
  │
  └─► Actualizar files.json (Local Nodo 1) ✅

Si Routing Mesh envía a Backend en Nodo 2:
  │ POST /files
  ▼
Backend (Nodo 2)
  │
  └─► ❌ ERROR: No puede acceder a /tags_data/files/
      (Volumen local solo en Nodo 1)
```

### DESPUÉS (Distribuido)
```
Usuario
  │
  ▼
Frontend (Cualquier nodo)
  │ POST /files
  ▼
Routing Mesh → Backend (Cualquier réplica)
  │
  ├─► Guardar archivo en NFS:/srv/nfs/tagfs_data/files/ ✅
  │   (Accesible desde TODOS los nodos)
  │
  ├─► Actualizar files.json en NFS ✅
  │   (Visible para TODOS los backends)
  │
  └─► Insertar en PostgreSQL ✅
      (BD compartida, accesible por todos)

✅ Funciona desde CUALQUIER réplica en CUALQUIER nodo
```

---

## 🔄 FLUJO DE DATOS - Login de Usuario

### ANTES (Problemático)
```
Usuario → Frontend
  │ POST /auth/login
  ▼
Backend (Nodo 1)
  │
  └─► SQLite (Local Nodo 1) → ✅ Token JWT

Usuario → Frontend
  │ POST /auth/login
  ▼
Backend (Nodo 2)
  │
  └─► ❌ ERROR: SQLite no accesible
      (Archivo solo en Nodo 1)
```

### DESPUÉS (Distribuido)
```
Usuario → Frontend
  │ POST /auth/login
  ▼
Backend (Cualquier réplica)
  │
  └─► PostgreSQL (Servicio compartido)
      │
      └─► ✅ Token JWT

✅ Funciona desde CUALQUIER backend
✅ Datos consistentes en todo el cluster
```

---

## 🗂️ ESTRUCTURA DE ALMACENAMIENTO

### Opción 1: NFS (Recomendado para empezar)

```
NFS Server (Nodo Manager)
/srv/nfs/
  └── tagfs_data/
      ├── files/
      │   ├── documento.pdf
      │   ├── foto.jpg
      │   └── video.mp4
      └── files.json
          {
            "documento.pdf": ["trabajo", "importante"],
            "foto.jpg": ["personal", "vacaciones"],
            "video.mp4": ["tutorial", "python"]
          }

Montado en todos los nodos como:
- Nodo 1: /app/tags_data → NFS
- Nodo 2: /app/tags_data → NFS
```

### Opción 2: GlusterFS (Más robusto)

```
GlusterFS Volume (Replicado 2x)
tagfs-volume
  ├── Brick 1 (Nodo 1): /data/brick1/
  │   ├── files/
  │   │   ├── documento.pdf
  │   │   ├── foto.jpg
  │   │   └── video.mp4
  │   └── files.json
  │
  └── Brick 2 (Nodo 2): /data/brick2/
      ├── files/              ← Replica automática
      │   ├── documento.pdf   ✅ Copia
      │   ├── foto.jpg        ✅ Copia
      │   └── video.mp4       ✅ Copia
      └── files.json          ✅ Copia

✅ Si un brick falla, el otro tiene TODOS los datos
✅ Replicación automática
```

---

## 🔐 PERSISTENCIA DE DATOS

### Datos que DEBEN ser compartidos

| Dato | Ubicación Actual | Ubicación Objetivo | Estrategia |
|------|------------------|-------------------|------------|
| **Archivos binarios** | `/tags_data/files/` (local) | NFS/GlusterFS | Volumen compartido |
| **files.json** | `/tags_data/files/files.json` (local) | NFS/GlusterFS | Volumen compartido |
| **users.db (SQLite)** | `/tags_data/users.db` (local) | PostgreSQL | Migrar a BD distribuida |
| **Logs** | Stdout/Stderr | Loki/ELK (opcional) | Logging centralizado |

### Configuración de Volúmenes

```yaml
# docker-stack-distributed-fixed.yml
version: '3.8'

services:
  # Base de datos compartida
  database:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: tagfs
      POSTGRES_USER: tagfs_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - tagfs-overlay
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

  # Backend con almacenamiento compartido
  backend:
    image: tagfs-backend:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://tagfs_user:changeme@database:5432/tagfs
      - PYTHONUNBUFFERED=1
    volumes:
      - tagfs-data:/app/tags_data
    networks:
      - tagfs-overlay
    depends_on:
      - database
    deploy:
      replicas: 3  # Múltiples réplicas
      restart_policy:
        condition: on-failure

  # Frontend
  frontend:
    image: tagfs-frontend:latest
    ports:
      - "80:80"
    networks:
      - tagfs-overlay
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure

networks:
  tagfs-overlay:
    driver: overlay
    attachable: true

volumes:
  # Volumen compartido NFS para archivos
  tagfs-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=172.20.10.4,rw,nfsvers=4
      device: ":/srv/nfs/tagfs_data"
  
  # Volumen compartido NFS para PostgreSQL
  postgres-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=172.20.10.4,rw,nfsvers=4
      device: ":/srv/nfs/postgres_data"
```

---

## 🚀 ESCALABILIDAD

### Escenario 1: Carga Baja (2 nodos)
```
┌─────────┐     ┌─────────┐
│ Nodo 1  │     │ Nodo 2  │
├─────────┤     ├─────────┤
│ Back x2 │     │ Front x2│
│ Front x2│     │ Back x2 │
│ DB x1   │     │         │
└────┬────┘     └────┬────┘
     └──────┬────────┘
            │
         NFS Storage
```

### Escenario 2: Carga Media (3 nodos)
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Nodo 1  │  │ Nodo 2  │  │ Nodo 3  │
├─────────┤  ├─────────┤  ├─────────┤
│ Back x2 │  │ Back x2 │  │ Back x2 │
│ DB x1   │  │ Front x2│  │ Front x2│
└────┬────┘  └────┬────┘  └────┬────┘
     └───────────┬────────────┘
                 │
            GlusterFS
          (Replicado 3x)
```

### Escenario 3: Alta Disponibilidad (4+ nodos)
```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│Manager 1│  │Manager 2│  │Worker 1 │  │Worker 2 │
├─────────┤  ├─────────┤  ├─────────┤  ├─────────┤
│ Back x2 │  │ Back x2 │  │ Back x3 │  │ Front x3│
│ DB x1   │  │ DB Repl │  │ Front x2│  │         │
│ Redis   │  │ Redis R │  │         │  │         │
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
     └──────────────┬──────────────────────┘
                    │
               GlusterFS
             (Replicado 4x)
```

---

## 🔍 COMPARACIÓN DE TECNOLOGÍAS

### Almacenamiento Compartido

| Tecnología | Pros | Contras | Complejidad | Recomendado para |
|------------|------|---------|-------------|------------------|
| **NFS** | Simple, bien soportado | Single point of failure | Baja | 2-3 nodos, desarrollo |
| **GlusterFS** | Replicación, HA nativa | Más recursos, complejo | Media | 3+ nodos, producción |
| **Ceph** | Muy robusto, escalable | Muy complejo, recursos | Alta | 5+ nodos, enterprise |
| **Volume Plugin** | Integración nativa | Requiere cloud/infraestructura | Media | Cloud (AWS/GCP/Azure) |

### Base de Datos

| Tecnología | Pros | Contras | Complejidad | Recomendado para |
|------------|------|---------|-------------|------------------|
| **SQLite** | Simple, sin servidor | ❌ No distribuido | Muy baja | Solo desarrollo local |
| **PostgreSQL** | Robusto, ACID, bien soportado | Requiere servidor | Baja | Tu proyecto ✅ |
| **PostgreSQL + Replication** | HA, escalable lectura | Configuración compleja | Media-Alta | Producción crítica |
| **MySQL** | Popular, buen rendimiento | Similar a PostgreSQL | Baja | Alternativa válida |
| **MongoDB** | Flexible, escalable | No relacional, curva aprendizaje | Media | Datos no estructurados |

---

## 📈 MIGRACIÓN PASO A PASO

### Fase 1: Preparación (Día 1)
```bash
# 1. Backup de datos actuales
tar -czf backup-$(date +%Y%m%d).tar.gz tags_data/

# 2. Configurar NFS
sudo apt install nfs-kernel-server
sudo mkdir -p /srv/nfs/tagfs_data
sudo mkdir -p /srv/nfs/postgres_data

# 3. Configurar exports
echo "/srv/nfs/tagfs_data *(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports
echo "/srv/nfs/postgres_data *(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports

# 4. Aplicar
sudo exportfs -a
sudo systemctl restart nfs-kernel-server
```

### Fase 2: Migración de Datos (Día 2)
```bash
# 1. Copiar archivos existentes a NFS
sudo cp -r tags_data/* /srv/nfs/tagfs_data/

# 2. Verificar
ls -la /srv/nfs/tagfs_data/files/
cat /srv/nfs/tagfs_data/files/files.json

# 3. Montar en worker
# (En worker)
sudo mount 172.20.10.4:/srv/nfs/tagfs_data /mnt/tagfs_data
```

### Fase 3: PostgreSQL (Día 3)
```bash
# 1. Actualizar requirements.txt
echo "psycopg2-binary" >> requirements.txt

# 2. Reconstruir imagen
docker build -t tagfs-backend:latest -f Dockerfile.backend .

# 3. Desplegar con PostgreSQL
docker stack deploy -c docker-stack-distributed-fixed.yml tagfs

# 4. Migrar usuarios
docker exec -it $(docker ps -q -f name=tagfs_backend) python migrate_to_postgres.py
```

### Fase 4: Validación (Día 4-5)
```bash
# Testing completo
./test-distributed-system.sh
```

---

## 🎯 PRÓXIMOS PASOS

1. ✅ **Leer esta documentación completa**
2. 📝 **Decidir:** NFS o GlusterFS
3. 🔧 **Implementar:** Fase 1 y 2 (almacenamiento + BD)
4. 🧪 **Probar:** Escenarios de fallo
5. 📊 **Monitorear:** Agregar Grafana/Prometheus (opcional)
6. 📖 **Documentar:** Decisiones y configuración

---

**Tiempo estimado:** 5 días para sistema distribuido funcional
**Complejidad:** Media (con esta documentación)

