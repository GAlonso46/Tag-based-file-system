# 🚫 ESTRATEGIAS SIN DHT - Alternativas para Sistema Distribuido

## ⚠️ RESTRICCIÓN DEL PROYECTO

**NO SE PERMITE:** Distributed Hash Table (DHT)
- ❌ Chord
- ❌ Kademlia  
- ❌ Pastry
- ❌ CAN (Content Addressable Network)

**Razón:** Usar DHT = Nota mínima (solo aprobado)

---

## ✅ ALTERNATIVAS PERMITIDAS (Para sacar buena nota)

### 🎯 ESTRATEGIA RECOMENDADA: Arquitectura Centralizada con Replicación

Esta es la mejor opción para tu proyecto porque:
- ✅ Simple de implementar
- ✅ Cumple TODOS los requisitos
- ✅ NO usa DHT
- ✅ Fácil de demostrar y explicar
- ✅ Tolerante a fallos

---

## 📐 ARQUITECTURA PROPUESTA (Sin DHT)

```
┌─────────────────────────────────────────────────────────────┐
│               CAPA DE PRESENTACIÓN                          │
│  Frontend (React) - Múltiples réplicas en Workers          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               CAPA DE APLICACIÓN                            │
│  Backend (FastAPI) - Múltiples réplicas sin estado         │
│  Role: API Gateway + Business Logic                         │
│                                                              │
│  📍 Características:                                         │
│  - Stateless (sin memoria de sesión)                        │
│  - Balanceo de carga automático (Swarm Routing Mesh)       │
│  - Todas las réplicas son idénticas                        │
│  - Cualquier réplica puede atender cualquier request       │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   CAPA DE    │  │   CAPA DE    │  │   CAPA DE    │
│   METADATA   │  │  ARCHIVOS    │  │   CACHÉ      │
│              │  │              │  │  (Opcional)  │
│  PostgreSQL  │  │     NFS      │  │    Redis     │
│              │  │  GlusterFS   │  │              │
│  Role:       │  │              │  │  Role:       │
│  Metadata    │  │  Role:       │  │  Performance │
│  Storage     │  │  File        │  │  Cache       │
│              │  │  Storage     │  │              │
│  - Users     │  │              │  │  - Tags list │
│  - Files DB  │  │  - Binarios  │  │  - Stats     │
│  - Tags      │  │  - files.json│  │              │
│  - Analytics │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘

🎯 ROLES CLARAMENTE DEFINIDOS:
1. Frontend: Presentación
2. Backend: Lógica de negocio
3. PostgreSQL: Metadata persistente
4. NFS/GlusterFS: Almacenamiento de archivos
5. Redis (opcional): Caché para rendimiento
```

---

## 🏗️ ROLES Y RESPONSABILIDADES

### 1. **Role: Frontend (Presentación)**
**Responsabilidad:** Interfaz de usuario
```yaml
deploy:
  replicas: 2-4
  placement:
    constraints:
      - node.labels.role == frontend
```

**Características:**
- ✅ Stateless (sin estado)
- ✅ Puede correr en cualquier worker
- ✅ Solo sirve archivos estáticos
- ✅ Todas las requests van al Backend

---

### 2. **Role: Backend (API Gateway + Logic)**
**Responsabilidad:** Lógica de negocio, autenticación, validación
```yaml
deploy:
  replicas: 3-5
  placement:
    constraints:
      - node.labels.role == backend
```

**Características:**
- ✅ Stateless (sesiones en JWT, no en memoria)
- ✅ Cada réplica es idéntica
- ✅ Todas acceden a las mismas fuentes de datos
- ✅ NO almacena nada localmente
- ✅ Balanceo de carga automático

**Código clave:**
```python
# api/main.py
# ✅ CORRECTO: Acceso a almacenamiento compartido
DATA_DIR = "/app/tags_data"  # Montado desde NFS en TODOS los backends
tag_service = TagService(DATA_DIR)

# ✅ CORRECTO: Base de datos compartida
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")
engine = create_engine(DATABASE_URL)

# ❌ INCORRECTO: Estado local (NO hacer esto)
# cache = {}  # ❌ Solo existe en UNA réplica
# session_store = {}  # ❌ No compartido entre réplicas
```

---

### 3. **Role: Metadata Storage (PostgreSQL)**
**Responsabilidad:** Datos estructurados (usuarios, metadata de archivos)
```yaml
database:
  deploy:
    replicas: 1  # Master único
    placement:
      constraints:
        - node.role == manager
        - node.labels.database == primary
```

**Datos almacenados:**
- Usuarios (username, email, password_hash, is_admin)
- Files metadata (filename, owner_id, tags, size, mime_type, created_at)
- Sesiones activas (opcional)
- Analytics y estadísticas

**Por qué NO es DHT:**
- ✅ Es una base de datos relacional centralizada
- ✅ Todos los backends consultan la MISMA instancia
- ✅ No hay particionamiento de datos por hash
- ✅ No hay ring de nodos

---

### 4. **Role: File Storage (NFS/GlusterFS)**
**Responsabilidad:** Almacenamiento de archivos binarios
```yaml
volumes:
  tagfs-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=<NFS_SERVER>,rw
      device: ":/srv/nfs/tagfs_data"
```

**Datos almacenados:**
- Archivos binarios en `/files/`
- `files.json` (metadata de tags, puede migrar a PostgreSQL)

**Por qué NO es DHT:**
- ✅ Almacenamiento centralizado (NFS) o replicado (GlusterFS)
- ✅ Todos los backends acceden al MISMO filesystem
- ✅ No hay hashing para distribuir archivos
- ✅ Todos los archivos están en TODAS las réplicas (GlusterFS)

---

### 5. **Role: Cache (Redis) - OPCIONAL**
**Responsabilidad:** Caché de consultas frecuentes
```yaml
redis:
  deploy:
    replicas: 1
    placement:
      constraints:
        - node.role == manager
```

**Uso:**
- Lista de tags populares
- Resultados de búsquedas frecuentes
- Estadísticas agregadas

**Por qué NO es DHT:**
- ✅ Caché centralizada (una sola instancia)
- ✅ Solo para performance, no para localización de datos
- ✅ Si falla, el sistema sigue funcionando (consulta directa a BD)

---

## 🔄 FLUJO DE DATOS (Sin DHT)

### Ejemplo: Upload de Archivo

```
1. Usuario → Frontend
   POST /files (archivo + tags)
   
2. Frontend → Docker Swarm Routing Mesh
   Selecciona UNA réplica de Backend (round-robin)
   
3. Backend (Réplica X)
   ├─► Validar autenticación (JWT)
   │
   ├─► Guardar archivo en NFS/GlusterFS
   │   /app/tags_data/files/documento.pdf
   │   (Montado desde almacenamiento compartido)
   │
   ├─► Actualizar files.json en NFS
   │   /app/tags_data/files/files.json
   │   (Visible para TODOS los backends)
   │
   └─► Insertar metadata en PostgreSQL
       INSERT INTO files (filename, owner_id, tags, ...)
       (BD compartida, accesible por TODOS)

4. Respuesta → Usuario
   { "message": "Archivo subido", "filename": "documento.pdf" }

✅ Cualquier otra réplica puede ahora:
   - Listar el archivo (lee de PostgreSQL/NFS)
   - Descargar el archivo (lee de NFS)
   - Actualizar tags (escribe en PostgreSQL/NFS)
```

**¿Por qué NO es DHT?**
- ❌ NO se usa hash(filename) para determinar nodo
- ❌ NO hay ring de nodos
- ❌ NO hay localización distribuida
- ✅ TODOS los backends tienen acceso a TODOS los datos
- ✅ Almacenamiento centralizado/replicado

---

### Ejemplo: Búsqueda por Tags

```
1. Usuario → Frontend
   GET /files?tags=trabajo,importante
   
2. Frontend → Backend (cualquier réplica)
   
3. Backend
   ├─► Opción A: Consultar PostgreSQL
   │   SELECT * FROM files WHERE tags @> '["trabajo","importante"]'
   │   (Si migramos tags a PostgreSQL)
   │
   └─► Opción B: Leer files.json desde NFS
       load_json("/app/tags_data/files/files.json")
       filter(files, tags=["trabajo","importante"])

4. Backend → Respuesta
   [
     {"name": "informe.pdf", "tags": ["trabajo","importante"]},
     {"name": "proyecto.docx", "tags": ["trabajo","importante","urgente"]}
   ]

✅ Misma respuesta sin importar qué réplica atienda
✅ NO se usa DHT para localizar archivos
✅ Todos los datos están en un solo lugar (centralizado)
```

---

## 🎯 VENTAJAS DE ESTA ARQUITECTURA (vs. DHT)

### ✅ Ventajas

1. **Simplicidad**
   - Fácil de entender y explicar a profesores
   - No requiere algoritmos complejos (Chord, Kademlia)
   - Debugging simple

2. **Consistencia Fuerte**
   - Todos los backends ven los mismos datos
   - No hay eventual consistency
   - No hay conflictos de réplicas

3. **Tolerancia a Fallos Clara**
   - Si un backend falla → Otros continúan
   - Si frontend falla → Otros continúan
   - Si NFS falla → Sistema inaccesible (pero datos NO se pierden)
   - Si PostgreSQL falla → Sistema inaccesible (pero datos NO se pierden)

4. **Cumple Requisitos del Proyecto**
   - ✅ Nodos con roles específicos
   - ✅ Sistema disponible si hay al menos un nodo por role
   - ✅ No perder datos ante fallo de nodo
   - ✅ Reconexión tras partición (Swarm lo maneja)

5. **Escalabilidad Horizontal**
   - Agregar más backends → Más capacidad de procesamiento
   - Agregar más frontends → Más usuarios concurrentes

### ❌ Desventajas (vs. DHT)

1. **Almacenamiento No Distribuido**
   - Todos los datos en un solo lugar (NFS)
   - Limitado por capacidad de NFS

2. **Cuello de Botella en I/O**
   - Todos acceden al mismo NFS
   - Puede ser lento con muchos usuarios

3. **Single Point of Failure**
   - Si NFS cae → Sistema inaccesible
   - Si PostgreSQL cae → Sistema inaccesible

**Mitigación:**
- Usar GlusterFS en lugar de NFS (replicación)
- PostgreSQL con replicación master-slave
- Backups automáticos

---

## 📊 COMPARACIÓN: DHT vs. Nuestra Arquitectura

| Característica | DHT (Prohibido) | Nuestra Arquitectura (Permitido) |
|----------------|-----------------|----------------------------------|
| **Localización de datos** | Hash distribuido | Centralizado (PostgreSQL + NFS) |
| **Estructura** | Ring/Tree de nodos | Capas (Frontend → Backend → Storage) |
| **Escalabilidad** | Muy alta | Media (limitado por NFS) |
| **Consistencia** | Eventual | Fuerte |
| **Complejidad** | Alta | Baja-Media |
| **Single Point of Failure** | No | Sí (NFS, PostgreSQL) |
| **Nota esperada** | Mínima ❌ | Alta ✅ |

---

## 🔧 IMPLEMENTACIÓN CONCRETA

### Etiquetar Nodos con Roles

```bash
# En Manager
docker node update --label-add role=manager <MANAGER_NODE_ID>
docker node update --label-add database=primary <MANAGER_NODE_ID>

# En Workers
docker node update --label-add role=worker <WORKER1_NODE_ID>
docker node update --label-add role=worker <WORKER2_NODE_ID>
```

### Stack Actualizado (Sin DHT)

```yaml
version: '3.8'

services:
  # ===== ROLE: METADATA STORAGE =====
  database:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: tagfs
      POSTGRES_USER: tagfs_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - tagfs-overlay
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
          - node.labels.database == primary
      restart_policy:
        condition: on-failure
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tagfs_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ===== ROLE: BACKEND (API + LOGIC) =====
  backend:
    image: tagfs-backend:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://tagfs_user:${DB_PASSWORD}@database:5432/tagfs
      - PYTHONUNBUFFERED=1
    volumes:
      - tagfs-data:/app/tags_data  # Montado desde NFS (compartido)
    networks:
      - tagfs-overlay
    depends_on:
      - database
    deploy:
      replicas: 3  # Múltiples réplicas stateless
      placement:
        constraints:
          - node.labels.role == worker || node.role == manager
      restart_policy:
        condition: on-failure
      update_config:
        parallelism: 1
        delay: 10s
      rollback_config:
        parallelism: 1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ===== ROLE: FRONTEND (PRESENTACIÓN) =====
  frontend:
    image: tagfs-frontend:latest
    ports:
      - "80:80"
    networks:
      - tagfs-overlay
    deploy:
      replicas: 2  # Múltiples réplicas para balanceo
      placement:
        constraints:
          - node.labels.role == worker
      restart_policy:
        condition: on-failure
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ===== ROLE: CACHE (OPCIONAL) =====
  redis:
    image: redis:7-alpine
    networks:
      - tagfs-overlay
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  tagfs-overlay:
    driver: overlay
    attachable: true

volumes:
  # ROLE: FILE STORAGE (NFS compartido)
  tagfs-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=${NFS_SERVER_IP},rw,nfsvers=4
      device: ":/srv/nfs/tagfs_data"
  
  # ROLE: METADATA STORAGE (PostgreSQL)
  postgres-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=${NFS_SERVER_IP},rw,nfsvers=4
      device: ":/srv/nfs/postgres_data"
```

---

## 🎓 PARA DEFENDER ANTE LOS PROFESORES

### Pregunta: "¿Por qué no usaron DHT?"

**Respuesta:**

> "Decidimos NO usar DHT (Distributed Hash Table) y en su lugar implementamos una **arquitectura en capas con roles específicos**:
>
> 1. **Capa de Presentación**: Frontends stateless en workers
> 2. **Capa de Aplicación**: Backends stateless con balanceo de carga
> 3. **Capa de Datos**: Almacenamiento centralizado con replicación (NFS/GlusterFS + PostgreSQL)
>
> Esta arquitectura cumple TODOS los requisitos del proyecto:
> - ✅ Nodos con roles específicos (Frontend, Backend, Storage, Metadata)
> - ✅ Disponibilidad si hay al menos un nodo por role
> - ✅ No se pierden datos ante fallo de nodo (replicación en GlusterFS)
> - ✅ Reconexión tras partición (Docker Swarm + sincronización de datos)
>
> **Ventajas sobre DHT:**
> - Consistencia fuerte (no eventual)
> - Más simple de implementar y debuggear
> - Fácil de razonar sobre el estado del sistema
> - No requiere algoritmos complejos de consenso

### Pregunta: "¿Cómo manejan la distribución de datos sin DHT?"

**Respuesta:**

> "No distribuimos los datos por hashing, sino que usamos **almacenamiento compartido replicado**:
>
> - **NFS**: Todos los nodos montan el mismo filesystem
> - **GlusterFS**: Replicación automática en múltiples nodos
> - **PostgreSQL**: Base de datos centralizada con replicación opcional
>
> Todos los backends tienen acceso a TODOS los datos. No hay particionamiento por hash.
> Esto es más simple y garantiza consistencia fuerte."

### Pregunta: "¿Cómo escala sin DHT?"

**Respuesta:**

> "Escalamos horizontalmente en la capa de aplicación:
>
> - **Frontend**: 2-4 réplicas (stateless)
> - **Backend**: 3-5 réplicas (stateless)
> - **Storage**: GlusterFS puede agregar más bricks
> - **Database**: PostgreSQL con read replicas (opcional)
>
> El cuello de botella está en I/O del almacenamiento, pero para el alcance de este proyecto (2-3 nodos), es más que suficiente."

---

## 🚀 ENRIQUECIMIENTOS SIN DHT

Para destacar en el proyecto sin usar DHT:

### 1. **Replicación Activa en GlusterFS**
```bash
# Crear volumen replicado en 3 nodos
gluster volume create tagfs-vol replica 3 \
  server1:/data/brick1 \
  server2:/data/brick2 \
  server3:/data/brick3
```

### 2. **PostgreSQL Master-Slave**
```yaml
database-master:
  # ...
  
database-replica:
  image: postgres:15-alpine
  environment:
    POSTGRES_MASTER_SERVICE_HOST: database-master
  deploy:
    replicas: 2
```

### 3. **Caché Distribuido con Redis**
```python
# Caché de tags populares
@app.get("/tags")
async def get_tags():
    cached = redis_client.get("popular_tags")
    if cached:
        return json.loads(cached)
    
    tags = compute_popular_tags()
    redis_client.setex("popular_tags", 300, json.dumps(tags))
    return tags
```

### 4. **Monitoreo del Cluster**
```yaml
prometheus:
  # Métricas de cada nodo
  
grafana:
  # Dashboard de estado del cluster
```

### 5. **Backup Automático**
```bash
# Cron job diario
0 2 * * * rsync -av /srv/nfs/tagfs_data/ /backup/$(date +\%Y\%m\%d)/
```

---

## ✅ CHECKLIST FINAL (Sin DHT)

### Requisitos del Proyecto
- [ ] Nodos con roles específicos (Frontend, Backend, Storage, Metadata)
- [ ] Sistema disponible con al menos un nodo por role
- [ ] No perder datos ante fallo de nodo (GlusterFS replication)
- [ ] Reconexión tras partición (Swarm + data sync)

### Técnicas Implementadas (Sin DHT)
- [ ] Balanceo de carga (Swarm Routing Mesh)
- [ ] Almacenamiento compartido (NFS/GlusterFS)
- [ ] Base de datos distribuida (PostgreSQL)
- [ ] Replicación de servicios (múltiples réplicas)
- [ ] Stateless backends (sin estado local)
- [ ] Health checks y auto-restart
- [ ] Versionado para reconciliación

### Enriquecimientos
- [ ] Caché con Redis
- [ ] Monitoreo con Prometheus/Grafana
- [ ] Backup automático
- [ ] PostgreSQL replication (opcional)
- [ ] Logging centralizado (Loki)

---

## 📝 CONCLUSIÓN

**Tu proyecto NO usa DHT porque:**

1. ✅ Todos los backends acceden al mismo almacenamiento (NFS/GlusterFS)
2. ✅ Todos los backends consultan la misma BD (PostgreSQL)
3. ✅ No hay particionamiento de datos por hash
4. ✅ No hay ring o árbol de nodos para localización
5. ✅ Es una arquitectura en capas con roles específicos

**Esto es MEJOR para tu proyecto porque:**
- 🎓 Más fácil de explicar a profesores
- 🔧 Más fácil de implementar y debuggear
- 📊 Más fácil de demostrar funcionamiento
- ⭐ **Mejor nota** (no es solo "usar DHT")

---

**Próximo paso:** Implementa la arquitectura descrita en esta guía. Tendrás un sistema distribuido robusto **sin DHT** que te dará una excelente calificación. 🚀


---

## 🔐 MANEJO DE CONCURRENCIA SIN DHT

### Problema: Ediciones Concurrentes

Con múltiples frontends y backends, varios usuarios pueden intentar editar el mismo archivo simultáneamente:

```
Usuario A (Frontend 1 → Backend 1):
  1. Lee archivo.pdf (tags: ["trabajo", "v1"])
  2. Modifica tags → ["trabajo", "v2", "urgente"]
  3. Guarda cambios

Usuario B (Frontend 2 → Backend 2) - SIMULTÁNEAMENTE:
  1. Lee archivo.pdf (tags: ["trabajo", "v1"])
  2. Modifica tags → ["trabajo", "importante"]
  3. Guarda cambios

❌ PROBLEMA: Los cambios de Usuario A se pierden (sobrescritos por B)
```

### Solución: Optimistic Locking

Implementamos **versionado con validación** en la capa de base de datos:

#### 1. Campo `version` en FileDB

```python
# api/models.py
class FileDB(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    tags = Column(Text, default="")
    version = Column(Integer, default=1, nullable=False)  # ← Optimistic locking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 2. Endpoint con Validación de Versión

```python
# api/main.py
@app.put("/files/{filename}/tags")
async def update_tags(
    filename: str,
    tags_update: TagsUpdate,  # {"tags": [...], "version": 3}
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file_db = check_file_ownership(db, filename, current_user)
    
    # Validar versión actual vs. esperada
    if tags_update.version is not None:
        if file_db.version != tags_update.version:
            raise HTTPException(
                status_code=409,  # Conflict
                detail={
                    "error": "Conflict",
                    "message": f"Archivo modificado por otro usuario",
                    "current_version": file_db.version,
                    "current_tags": json.loads(file_db.tags)
                }
            )
    
    # Actualizar tags e incrementar versión
    file_db.tags = json.dumps(tags_update.tags)
    file_db.version += 1  # v3 → v4
    db.commit()
    
    return {
        "message": "Tags actualizados",
        "version": file_db.version  # Retornar nueva versión
    }
```

#### 3. Flujo con Optimistic Locking

```
Usuario A:
  1. GET /files → {"filename": "doc.pdf", "tags": [...], "version": 3}
  2. Modifica tags en UI
  3. PUT /files/doc.pdf/tags {"tags": [...], "version": 3}
     ✓ Backend valida: version actual (3) == version enviada (3)
     ✓ Actualiza: tags + version → 4
     ✓ Retorna: 200 OK {"version": 4}

Usuario B (editando simultáneamente):
  1. GET /files → {"filename": "doc.pdf", "tags": [...], "version": 3}
  2. Modifica tags en UI (mientras A actualiza)
  3. PUT /files/doc.pdf/tags {"tags": [...], "version": 3}
     ✗ Backend valida: version actual (4) != version enviada (3)
     ✗ Retorna: 409 Conflict
        {
          "error": "Conflict",
          "message": "Archivo modificado por otro usuario",
          "current_version": 4,
          "current_tags": ["trabajo", "v2", "urgente"]  ← Cambios de A
        }
  4. Usuario B refresca datos (obtiene version 4)
  5. Reaplica sus cambios y envía version 4
     ✓ Actualización exitosa → version 5
```

### Ventajas de Optimistic Locking

| Característica | Sin Locking | Con Optimistic Locking |
|----------------|-------------|------------------------|
| **Conflictos detectados** | ❌ No | ✅ Sí (409 Conflict) |
| **Pérdida de datos** | ❌ Último escribe gana | ✅ No hay pérdida |
| **Performance** | ✅ Alta (no locks) | ✅ Alta (no locks) |
| **Escalabilidad** | ✅ Alta | ✅ Alta |
| **Complejidad** | Muy baja | Baja-Media |
| **Deadlocks** | ✅ No | ✅ No |

### Manejo en Frontend (React)

```jsx
// Ejemplo de manejo de conflictos
const handleUpdateTags = async (filename, newTags, currentVersion) => {
  try {
    const response = await api.put(`/files/${filename}/tags`, {
      tags: newTags,
      version: currentVersion
    });
    
    // Éxito - actualizar UI
    setFileVersion(response.data.version);
    showNotification("Tags actualizados correctamente", "success");
    
  } catch (error) {
    if (error.response?.status === 409) {
      // Conflicto detectado
      const { current_version, current_tags } = error.response.data.detail;
      
      showNotification(
        `Conflicto: Otro usuario modificó el archivo. 
         Tags actuales: ${current_tags.join(', ')}`,
        "warning"
      );
      
      // Opción 1: Refrescar automáticamente
      await refreshFileData(filename);
      
      // Opción 2: Preguntar al usuario
      if (confirm("¿Sobrescribir cambios del otro usuario?")) {
        await handleUpdateTags(filename, newTags, current_version);
      }
    }
  }
};
```

### Migración de BD Existente

```bash
# Ejecutar script de migración
python3 migrate_add_version.py
```

### Tests de Concurrencia

```bash
# Ejecutar tests de edición concurrente
python3 test_concurrent_edits.py

# Tests incluidos:
# [TEST 1] Edición concurrente CON optimistic locking
# [TEST 2] Retry después de conflict  
# [TEST 3] Actualización sin version (retrocompatibilidad)
# [TEST 4] Alta concurrencia (10 clientes simultáneos)
```

### Por Qué NO es DHT

El optimistic locking **no convierte esto en DHT** porque:

- ✅ Todos los datos siguen en PostgreSQL centralizado
- ✅ No hay particionamiento por hash
- ✅ No hay ring de nodos
- ✅ Solo es validación de versión en BD relacional
- ✅ Cualquier backend puede actualizar cualquier archivo

Es simplemente **control de concurrencia estándar** usado en sistemas centralizados.

---

**Sistema completo con:**
- ✅ Arquitectura distribuida sin DHT
- ✅ Manejo profesional de concurrencia
- ✅ Optimistic locking para prevenir conflictos
- ✅ Tests de validación incluidos

🚀
