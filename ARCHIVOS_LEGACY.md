# Archivos Legacy / Innecesarios para Sistema Distribuido

Este directorio contiene archivos que ya no se usan en el sistema distribuido
pero se mantienen por compatibilidad o referencia histórica.

## Scripts PowerShell (Windows - No necesarios en Linux/VM)
- `build-images.ps1` - Reemplazado por `build-images.sh` y `deploy.sh`
- `start-react.ps1` - Reemplazado por Docker Swarm
- `test-integration.ps1` - No usado en producción

## CLI Legacy (Ya no se actualiza)
- `main.py` - CLI interactivo original (pre-API)
- `Dockerfile.cli` - Docker para CLI
- `docker-service-cli.yml` - Servicio CLI
- `docker-service-cli-local.yml` - Servicio CLI local
- `docker-stack-with-cli.yml` - Stack con CLI incluido

## Scripts de Migración Viejos (Reemplazados)
- `migrate_admin.py` - Migración antigua de admin (usar `migrate_sqlite_to_postgres.py`)
- `migrate_add_admin_column.py` - Migración de columna (ya incluido en models)
- `migrate_to_postgres.py` - Versión simple (usar `migrate_sqlite_to_postgres.py`)
- `inspect_db.py` - Script de debug SQLite (obsoleto con PostgreSQL)

## Frontend HTML Legacy
- `frontend/` - Frontend HTML simple (reemplazado por `frontend-react/`)
  - `index.html` - Versión antigua sin React
  - `login.html` - Login standalone

## Configuraciones Docker Alternativas (No usadas actualmente)
- `docker-compose.yml` - Para desarrollo local (no distribuido)
- `docker-stack.yml` - Stack genérico (usar `docker-stack-distributed.yml`)
- `docker-stack-flexible.yml` - Sin placement constraints
- `docker-stack-single.yml` - Todo en un nodo
- `docker-service-backend.yml` - Servicio standalone
- `docker-service-frontend.yml` - Servicio standalone

## Utilidades
- `get-docker.sh` - Script de instalación Docker (manual)
- `run_api.py` - Runner local del API (sin Docker)

## Documentación Legacy
- `MULTI_MANAGER_SETUP.md` - Setup multi-manager (no implementado)

---

## Archivos que SÍ se usan (NO borrar)

### Scripts de Configuración
- `deploy.sh` ✅ - Script maestro de despliegue
- `setup-nfs-server.sh` ✅ - Configurar NFS en manager
- `setup-nfs-client.sh` ✅ - Configurar NFS en workers
- `build-images.sh` ✅ - Construir imágenes Docker

### Migración de Datos
- `migrate_sqlite_to_postgres.py` ✅ - Migración completa

### Docker
- `Dockerfile.backend` ✅ - Imagen del backend
- `docker-stack-distributed.yml` ✅ - Stack principal
- `.dockerignore` ✅

### Aplicación
- `api/` ✅ - Backend FastAPI
- `frontend-react/` ✅ - Frontend React
- `tags/` ✅ - Lógica de negocio
- `requirements.txt` ✅ - Dependencias Python

### Documentación Nueva
- `README.md` ✅ - Documentación principal
- `README_DISTRIBUIDO.md` ✅ - Guía de inicio rápido
- `ESTRATEGIAS_SIN_DHT.md` ✅ - Arquitectura sin DHT
- `ARQUITECTURA_DETALLADA.md` ✅ - Diseño técnico
- `HOJA_DE_RUTA_DISTRIBUIDO.md` ✅ - Guía completa
- `DEFENSA_PROYECTO.md` ✅ - Para presentar
- `INDICE_DOCUMENTACION.md` ✅ - Índice
- `DOCKER_SWARM_SETUP.md` ✅ - Setup Swarm

### Configuración
- `.gitignore` ✅
- `LICENSE` ✅

---

## Recomendaciones de Limpieza

### Opción 1: Archivar (Recomendado)
Crear carpeta `_legacy/` y mover archivos no usados:
```bash
mkdir -p _legacy
mv main.py _legacy/
mv Dockerfile.cli _legacy/
mv frontend/ _legacy/
# ... etc
```

### Opción 2: Eliminar completamente
Solo si estás seguro de que no los necesitas:
```bash
rm -rf frontend/
rm main.py Dockerfile.cli
rm docker-stack-single.yml docker-stack-flexible.yml
# ... etc
```

### Opción 3: Mantener todo
Dejar como está por compatibilidad y referencia histórica.
