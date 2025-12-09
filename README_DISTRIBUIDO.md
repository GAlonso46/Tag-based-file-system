# 🚀 Sistema Distribuido - Guía Rápida de Inicio

## ⚠️ IMPORTANTE: Restricción DHT

**NO SE PERMITE** usar Distributed Hash Table (DHT). 
Usamos arquitectura en capas con almacenamiento compartido en su lugar.

📖 **Ver:** `ESTRATEGIAS_SIN_DHT.md` para detalles completos.

---

## 📚 Documentación Disponible

| Documento | Propósito | Tiempo Lectura |
|-----------|-----------|----------------|
| **`INDICE_DOCUMENTACION.md`** | 📑 Índice completo | 5 min |
| **`ESTRATEGIAS_SIN_DHT.md`** | 🚫 Por qué NO DHT | 15 min |
| **`RESUMEN_EJECUTIVO.md`** | ⚡ Plan rápido | 10 min |
| **`ARQUITECTURA_DETALLADA.md`** | 🏗️ Diseño técnico | 30 min |
| **`HOJA_DE_RUTA_DISTRIBUIDO.md`** | 🗺️ Guía completa | 45 min |
| **`DEFENSA_PROYECTO.md`** | 🎓 Para presentar | 20 min |

---

## ⚡ DESPLIEGUE AUTOMATIZADO (Recomendado)

### Opción 1: Script Maestro (Un solo comando)

#### En el Nodo Manager:
```bash
# Dar permisos de ejecución
chmod +x deploy.sh setup-nfs-server.sh setup-nfs-client.sh

# Ejecutar despliegue completo
# Sintaxis: sudo bash deploy.sh manager <IP_MANAGER> <DB_PASSWORD>
sudo bash deploy.sh manager 172.20.10.4 mi_password_segura
```

Este script automáticamente:
- ✅ Configura servidor NFS
- ✅ Migra datos existentes a NFS
- ✅ Inicializa Docker Swarm
- ✅ Construye imágenes Docker
- ✅ Despliega el stack completo
- ✅ Muestra token para workers

#### En cada Nodo Worker:
```bash
# Dar permisos de ejecución
chmod +x deploy.sh setup-nfs-client.sh

# Configurar worker
sudo bash deploy.sh worker 172.20.10.4
```

Este script automáticamente:
- ✅ Configura cliente NFS
- ✅ Instala Docker si no existe
- ✅ Monta volúmenes compartidos
- ✅ Muestra comando para unirse al Swarm

#### Unir Worker al Swarm:
```bash
# Usa el token que mostró el script del manager
docker swarm join --token SWMTKN-1-xxxxx... 172.20.10.4:2377
```

#### Migrar Datos a PostgreSQL:
```bash
# Esperar a que PostgreSQL esté listo (30-60 segundos)
docker service ps tagfs_database

# Ejecutar migración
export DATABASE_URL="postgresql://tagfs_user:mi_password_segura@localhost:5432/tagfs"
python3 migrate_sqlite_to_postgres.py
```

---

## 🔧 DESPLIEGUE MANUAL (Paso a Paso)

### 1. Configurar NFS en Manager (5 min)
```bash
# Ejecutar script
sudo bash setup-nfs-server.sh
```

### 2. Configurar NFS en Workers (3 min)
```bash
# En cada worker (reemplaza IP)
sudo bash setup-nfs-client.sh 172.20.10.4
```

### 3. Migrar Datos Existentes (2 min)
```bash
# En manager
sudo cp -r tags_data/* /srv/nfs/tagfs_data/
```

### 4. Construir Imágenes Docker (5 min)
```bash
# Backend
docker build -t tagfs-backend:latest -f Dockerfile.backend .

# Frontend
cd frontend-react
docker build --build-arg VITE_API_URL="http://172.20.10.4:8000" -t tagfs-frontend:latest .
cd ..
```

### 5. Desplegar Stack (2 min)
```bash
# Exportar variables
export NFS_SERVER_IP=172.20.10.4
export DB_PASSWORD=mi_password_segura

# Desplegar
docker stack deploy -c docker-stack-distributed.yml tagfs
```

### 6. Migrar Datos a PostgreSQL (3 min)
```bash
# Esperar a que PostgreSQL esté listo
docker service logs -f tagfs_database

# Cuando veas "database system is ready to accept connections"
export DATABASE_URL="postgresql://tagfs_user:mi_password_segura@localhost:5432/tagfs"
python3 migrate_sqlite_to_postgres.py
```

---

## � Verificación del Sistema

### Ver Estado de Servicios:
```bash
docker service ls
# Debería mostrar:
# tagfs_frontend      replicated  2/2
# tagfs_backend       replicated  3/3
# tagfs_database      replicated  1/1

docker service ps tagfs_backend
```

### Ver Logs:
```bash
# Backend
docker service logs -f tagfs_backend

# Base de datos
docker service logs -f tagfs_database

# Frontend
docker service logs -f tagfs_frontend
```

### Probar API:
```bash
# Registrar usuario
curl -X POST http://172.20.10.4:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Login
curl -X POST http://172.20.10.4:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Subir archivo
curl -X POST http://172.20.10.4:8000/files \
  -F "file=@test.pdf" \
  -F "tags=trabajo,importante"

# Listar archivos
curl http://172.20.10.4:8000/files?tags=trabajo
```

### Acceder Frontend:
```
http://172.20.10.4:3000
```

---

## 🛑 Solución de Problemas

### PostgreSQL no arranca:
```bash
# Ver logs
docker service logs tagfs_database

# Verificar volumen NFS
ls -la /srv/nfs/postgres_data

# Recrear servicio
docker service update --force tagfs_database
```

### NFS no monta:
```bash
# En manager, verificar exports
sudo exportfs -v

# Verificar firewall
sudo ufw allow from 172.20.10.0/24 to any port nfs

# En worker, probar montaje manual
sudo mount -v -t nfs4 172.20.10.4:/srv/nfs/tagfs_data /mnt/test
```

### Servicios no distribuyen:
```bash
# Ver placement constraints
docker service inspect tagfs_backend --pretty

# Ver nodos disponibles
docker node ls

# Forzar redistribución
docker service update --force tagfs_backend
```

### Migración falla:
```bash
# Verificar conexión PostgreSQL
export DATABASE_URL="postgresql://tagfs_user:PASSWORD@localhost:5432/tagfs"
python3 -c "from sqlalchemy import create_engine; create_engine('$DATABASE_URL').connect()"

# Verificar SQLite original
ls -la tags_data/tagfs.db

# Ejecutar migración con verbose
python3 migrate_sqlite_to_postgres.py 2>&1 | tee migration.log
```

---

## 📁 Scripts Disponibles

| Script | Propósito | Uso |
|--------|-----------|-----|
| `deploy.sh` | Despliegue completo | `sudo bash deploy.sh manager <IP> <PASS>` |
| `setup-nfs-server.sh` | Configurar NFS server | `sudo bash setup-nfs-server.sh` |
| `setup-nfs-client.sh` | Configurar NFS client | `sudo bash setup-nfs-client.sh <IP>` |
| `migrate_sqlite_to_postgres.py` | Migrar datos | `python3 migrate_sqlite_to_postgres.py` |

---

## 🗂️ Archivos Legacy

Los siguientes archivos fueron movidos a `_legacy/` (no se usan en versión distribuida):
- CLI local (`main.py`, `Dockerfile.cli`)
- Frontend HTML antiguo (`frontend/`)
- Scripts Windows (`.ps1`)
- Migraciones viejas

📖 **Ver:** `ARCHIVOS_LEGACY.md` para detalles completos.

---

## 🏗️ Arquitectura (Sin DHT)

```
┌─────────────────────────────────────┐
│  Frontend (React) x2                │  Role: Presentación
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Backend (FastAPI) x3               │  Role: API + Logic
│  - Stateless                        │  (NO DHT, todos iguales)
│  - JWT Auth                         │
└───────┬─────────────────┬───────────┘
        │                 │
┌───────▼────────┐  ┌────▼──────────┐
│  PostgreSQL    │  │  NFS/GlusterFS│  Roles: Storage
│  (Metadata)    │  │  (Files)      │  (Compartidos)
└────────────────┘  └───────────────┘

✅ TODOS los backends acceden a TODOS los datos
✅ NO hay particionamiento por hash (NO DHT)
✅ Replicación en NFS (o GlusterFS para alta disponibilidad)
```

---

## � Próximos Pasos

1. **Leer:** `INDICE_DOCUMENTACION.md` para navegación completa
2. **Estudiar:** `ESTRATEGIAS_SIN_DHT.md` antes de codificar (¡CRÍTICO!)
3. **Implementar:** Seguir `HOJA_DE_RUTA_DISTRIBUIDO.md` (fases 1-6)
4. **Preparar:** Estudiar `DEFENSA_PROYECTO.md` para presentación

---

## 🎓 Para la Presentación

**Puntos clave a mencionar:**

1. ✅ **NO usamos DHT** porque:
   - Complejidad innecesaria para 2-3 nodos
   - Consistencia más fácil con PostgreSQL
   - Replicación nativa con Docker Swarm

2. ✅ **Arquitectura en capas:**
   - Frontend stateless (2 réplicas)
   - Backend stateless (3 réplicas)
   - Almacenamiento centralizado (PostgreSQL + NFS)

3. ✅ **Tolerancia a fallos:**
   - Réplicas automáticas con Docker Swarm
   - Datos persistentes en NFS
   - Reconexión automática de workers

4. ✅ **Comandos implementados:**
   - `add`, `delete`, `list`
   - `add-tags`, `delete-tags`
   - Búsqueda por tags (consultas complejas)

📖 **Ver:** `DEFENSA_PROYECTO.md` para respuestas detalladas a preguntas del profesor.

---

## 📊 Checklist de Requisitos

- [x] `add file-list tag-list` - Añadir archivos con tags
- [x] `delete tag-query` - Eliminar archivos por query
- [x] `list tag-query` - Listar archivos por query
- [x] `add-tags tag-query tag-list` - Añadir tags a archivos
- [x] `delete-tags tag-query tag-list` - Eliminar tags de archivos
- [x] Nodos con roles específicos (Frontend/Backend/Database)
- [x] No perder datos ante fallo (NFS compartido)
- [x] Reconexión tras partición (Docker Swarm auto-recovery)
- [ ] Alta disponibilidad completa (GlusterFS - opcional)

---

## ⏱️ Estimación de Tiempo

- **Despliegue automatizado (deploy.sh):** 10-15 minutos
- **Despliegue manual (paso a paso):** 25-30 minutos
- **Migración de datos (SQLite → PostgreSQL):** 3-5 minutos
- **Pruebas y validación:** 15-20 minutos
- **Total:** ~45-60 minutos para sistema completo

---

**¿Dudas?** 
- Consulta `DEFENSA_PROYECTO.md` para preguntas frecuentes del profesor
- Consulta `INDICE_DOCUMENTACION.md` para navegación de documentación
- Consulta `ARCHIVOS_LEGACY.md` para entender qué archivos no se usan

**¡Todo listo para empezar!** 🚀
