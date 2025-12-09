# 🗂️ Sistema de Ficheros Basado en Etiquetas - Distribuido# 🏷️ Tag-Based File System



Sistema distribuido de gestión de archivos con búsqueda por etiquetas (tags), construido con arquitectura en capas para alta disponibilidad y tolerancia a fallos.Sistema de gestión de archivos basado en etiquetas con interfaz web moderna y API REST.



## ⚠️ RESTRICCIÓN IMPORTANTE![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)

![Python](https://img.shields.io/badge/python-3.10+-green.svg)

**NO se utiliza DHT (Distributed Hash Table)** en este proyecto, conforme a los requisitos del curso.![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)



En su lugar, implementamos:## 📋 Características

- ✅ Arquitectura en capas con roles específicos

- ✅ Almacenamiento centralizado/replicado (PostgreSQL + NFS)- ✅ **Subir archivos** con drag & drop

- ✅ Servicios stateless con Docker Swarm- 🔍 **Búsqueda inteligente** por múltiples tags (operador AND)

- ✅ Alta disponibilidad mediante réplicas- 🏷️ **Gestión de etiquetas** flexible (añadir, eliminar, editar)

- 📊 **Estadísticas en tiempo real** (archivos, tags, espacio usado)

📖 **Justificación completa:** Ver [`ESTRATEGIAS_SIN_DHT.md`](ESTRATEGIAS_SIN_DHT.md)- 🎨 **Interfaz moderna** tipo Google Drive/Pinterest

- 🚀 **API REST completa** con documentación automática

---- 💾 **Persistencia local** con JSON y sistema de archivos



## 🚀 Inicio Rápido---



### Opción 1: Despliegue Automatizado (Recomendado)## 🚀 Inicio Rápido



```bash### Opción A: Docker Compose (Recomendado para Producción) 🐳

# En el nodo Manager

sudo bash deploy.sh manager <IP_MANAGER> <DB_PASSWORD>```bash

# 1. Construir imágenes

# En cada nodo Workerdocker-compose build

sudo bash deploy.sh worker <IP_MANAGER>

# Luego ejecutar el comando docker swarm join que muestra el manager# 2. Iniciar servicios

```docker-compose up -d



**¡Listo!** El script automáticamente:# 3. Verificar estado

- Configura NFS compartidodocker-compose ps

- Inicializa Docker Swarm```

- Construye y despliega servicios

- Migra datos a PostgreSQLLa aplicación estará disponible en:

- Optimiza base de datos- 🌐 **Frontend**: http://localhost

- 📡 **Backend API**: http://localhost:8000

### Opción 2: Despliegue Manual- 📚 **API Docs**: http://localhost:8000/docs



Ver guía completa en [`README_DISTRIBUIDO.md`](README_DISTRIBUIDO.md)**Para detener:**

```bash

---docker-compose down

```

## 🏗️ Arquitectura

### Opción B: Docker Swarm (2 PCs Distribuidas) 🌐

```

┌──────────────────────┐Ver [**DOCKER_SWARM_GUIDE.md**](DOCKER_SWARM_GUIDE.md) para instrucciones completas.

│  Frontend (React)    │  ← Stateless, 2 réplicas

│  Puerto: 3000        │```bash

└──────────┬───────────┘# Construir imágenes

           │./build-images.sh  # Linux/Mac

┌──────────▼───────────┐# o

│  Backend (FastAPI)   │  ← Stateless, 3 réplicas.\build-images.ps1  # Windows

│  Puerto: 8000        │     (NO DHT)

└──────┬──────┬────────┘# Desplegar en Swarm

       │      │docker stack deploy -c docker-stack.yml tagfs

   ┌───▼──┐ ┌▼────────┐```

   │ PG   │ │   NFS   │  ← Almacenamiento compartido

   │ SQL  │ │   v4    │### Opción C: Script Automático (Desarrollo Local) ⭐

   └──────┘ └─────────┘

``````powershell

# 1. Instalar dependencias (solo la primera vez)

**Características clave:**pip install -r requirements.txt

- 🔄 **Sin DHT:** Todos los backends acceden al mismo almacenamiento

- 🛡️ **Alta disponibilidad:** Réplicas automáticas con Docker Swarm# 2. Ejecutar todo con un solo comando

- 💾 **Persistencia:** Datos en NFS + PostgreSQL.\start.ps1

- 🔐 **Autenticación:** JWT con roles (admin/usuario)```

- 🏷️ **Tags:** Búsqueda compleja con queries booleanas

¡Eso es todo! El script:

---- ✅ Inicia la API en una nueva ventana

- ✅ Espera a que esté lista

## 📋 Comandos Soportados- ✅ Abre el frontend automáticamente



| Comando | Descripción | Ejemplo API |### Opción D: Manual (Más Control)

|---------|-------------|-------------|

| `add` | Subir archivo con tags | `POST /files` |**⚠️ IMPORTANTE: Necesitas 2 terminales separadas**

| `delete` | Eliminar por query | `DELETE /files/{filename}` |

| `list` | Listar por tags | `GET /files?tags=trabajo,importante` |#### Terminal 1 - API (dejar abierta)

| `add-tags` | Añadir tags | `POST /files/{filename}/tags` |```powershell

| `delete-tags` | Remover tags | `DELETE /files/{filename}/tags` |# 1. Instalar dependencias (solo la primera vez)

pip install -r requirements.txt

---

# 2. Iniciar servidor API

## 🧪 Pruebas y Validaciónpython run_api.py



### Validar configuración (sin Docker)# ¡NO CIERRES ESTA TERMINAL!

```bash```

bash validate_setup.sh

```La API estará disponible en:

- 🌐 **API**: http://localhost:8000

### Ejecutar suite de tests- 📚 **Documentación interactiva**: http://localhost:8000/docs

```bash- 📖 **Documentación alternativa**: http://localhost:8000/redoc

bash test_distributed.sh <IP_MANAGER>

```#### Terminal 2 - Frontend (nueva terminal)

```powershell

Tests incluidos:# En una NUEVA terminal de PowerShell

- ✅ Servicios Docker Swarm activosstart frontend\index.html

- ✅ Health checks de API```

- ✅ Autenticación JWT

- ✅ Upload/download de archivos> 💡 **Tip**: Usa VS Code y abre 2 terminales integradas (botón "+" en el panel de terminales)

- ✅ Búsqueda por tags

- ✅ Estadísticas y analytics---

- ✅ Persistencia en NFS

- ✅ PostgreSQL operacional## 📁 Estructura del Proyecto



---```

Tag-based-file-system/

## 📁 Estructura del Proyecto├── 🎨 frontend/

│   └── index.html              # Interfaz web completa (single-page)

```│

├── api/                       # Backend FastAPI├── 🔧 api/

│   ├── main.py               # Endpoints REST│   ├── __init__.py

│   ├── database.py           # Conexión PostgreSQL│   └── main.py                 # API REST con FastAPI

│   ├── models.py             # Modelos SQLAlchemy│

│   └── auth.py               # Autenticación JWT├── 📦 tags/

├── frontend-react/           # Frontend React│   ├── cli/

│   └── src/│   │   ├── __init__.py

│       ├── components/       # Componentes UI│   │   └── app.py              # CLI original (legacy)

│       └── services/         # Cliente API│   ├── core/

├── tags/                     # Core del sistema de tags│   │   ├── __init__.py

│   ├── core/                 # Lógica de negocio│   │   └── tag_service.py      # Lógica de negocio

│   └── data/                 # FileStore│   ├── data/

├── deploy.sh                 # 🚀 Script maestro de deployment│   │   ├── __init__.py

├── setup-nfs-server.sh       # Configurar NFS en manager│   │   └── file_store.py       # Capa de persistencia

├── setup-nfs-client.sh       # Configurar NFS en workers│   ├── utils/

├── migrate_sqlite_to_postgres.py  # Migración de datos│   │   ├── __init__.py

├── optimize_postgres.py      # Optimización de índices│   │   └── helpers.py          # Utilidades

├── test_distributed.sh       # Suite de tests│   └── config.py               # Configuración

├── validate_setup.sh         # Validación de configuración│

├── docker-stack-distributed.yml  # Stack de Docker Swarm├── 📂 tags_data/

└── Dockerfile.backend        # Imagen del backend│   └── files/

```│       ├── files.json          # Metadata (tags por archivo)

│       └── [archivos subidos]  # Archivos binarios

---│

├── 🧪 tests/

## 📚 Documentación Completa│   └── test_db.py              # Tests unitarios

│

| Documento | Descripción |├── main.py                     # CLI legacy

|-----------|-------------|├── run_api.py                  # Script para ejecutar la API

| **[INDICE_DOCUMENTACION.md](INDICE_DOCUMENTACION.md)** | 📑 Índice de toda la documentación |├── requirements.txt            # Dependencias

| **[ESTRATEGIAS_SIN_DHT.md](ESTRATEGIAS_SIN_DHT.md)** | 🚫 Por qué NO usar DHT (CRÍTICO) |└── README.md                   # Este archivo

| **[README_DISTRIBUIDO.md](README_DISTRIBUIDO.md)** | ⚡ Guía rápida de despliegue |```

| **[ARQUITECTURA_DETALLADA.md](ARQUITECTURA_DETALLADA.md)** | 🏗️ Diseño técnico completo |

| **[HOJA_DE_RUTA_DISTRIBUIDO.md](HOJA_DE_RUTA_DISTRIBUIDO.md)** | 🗺️ Plan de implementación (6 fases) |---

| **[DEFENSA_PROYECTO.md](DEFENSA_PROYECTO.md)** | 🎓 Preparación para presentación |

| **[ARCHIVOS_LEGACY.md](ARCHIVOS_LEGACY.md)** | 📦 Archivos movidos a `_legacy/` |## 🎯 Endpoints de la API



---### 📤 Subir Archivo

```http

## 🛠️ Stack TecnológicoPOST /files

Content-Type: multipart/form-data

### Backend

- **FastAPI** - Framework REST APIfile: <archivo>

- **PostgreSQL 15** - Base de datos distribuidatags: "trabajo,importante,pdf"

- **SQLAlchemy** - ORM```

- **JWT** - Autenticación

- **Python 3.10**### 📋 Listar Archivos

```http

### FrontendGET /files

- **React 18** - UI LibraryGET /files?tags=trabajo,importante  # Filtrar por tags

- **Vite** - Build tool```

- **Axios** - Cliente HTTP

### ⬇️ Descargar Archivo

### Infraestructura```http

- **Docker Swarm** - OrquestaciónGET /files/{filename}

- **NFS v4** - Almacenamiento compartido```

- **Nginx** - Servidor web (frontend)

### 🗑️ Eliminar Archivo

---```http

DELETE /files/{filename}

## 🔧 Requisitos del Sistema```



### Mínimos (Pruebas locales)### ✏️ Actualizar Tags (reemplazar)

- 1 nodo con 2GB RAM```http

- Docker 20.10+PATCH /files/{filename}/tags

- Python 3.10+Content-Type: application/json

- 10GB espacio en disco

{

### Recomendados (Producción)  "tags": ["nuevo", "tags"]

- 3 nodos (1 manager + 2 workers)}

- 4GB RAM por nodo```

- 20GB espacio en disco

- Red con latencia < 10ms### ➕ Añadir Tags (sin eliminar existentes)

```http

---POST /files/{filename}/tags

Content-Type: application/json

## 📊 Monitoreo

{

### Ver estado de servicios  "tags": ["extra", "tags"]

```bash}

docker service ls```

docker service ps tagfs_backend

```### ➖ Eliminar Tags Específicos

```http

### Ver logsDELETE /files/{filename}/tags

```bashContent-Type: application/json

docker service logs -f tagfs_backend

docker service logs -f tagfs_database{

docker service logs -f tagfs_frontend  "tags": ["tag_a_eliminar"]

```}

```

### Escalar servicios

```bash### 🏷️ Obtener Todos los Tags

docker service scale tagfs_backend=5```http

docker service scale tagfs_frontend=3GET /tags

```

# Respuesta:

---{

  "tags": [

## 🐛 Troubleshooting    {"name": "trabajo", "count": 5},

    {"name": "importante", "count": 3}

### PostgreSQL no arranca  ],

```bash  "total": 2

# Ver logs}

docker service logs tagfs_database```



# Verificar volumen NFS### 📊 Estadísticas

ls -la /srv/nfs/postgres_data```http

GET /stats

# Recrear servicio

docker service update --force tagfs_database# Respuesta:

```{

  "total_files": 10,

### NFS no monta  "total_tags": 15,

```bash  "total_size_bytes": 2048000,

# En manager  "total_size_mb": 2.05

sudo exportfs -v}

sudo systemctl status nfs-kernel-server```



# En worker---

sudo mount -v -t nfs4 <IP>:/srv/nfs/tagfs_data /mnt/test

```## 🎨 Interfaz Web



### Servicios no distribuyen### Características de la UI:

```bash

# Ver placement constraints1. **🎯 Barra de Búsqueda**: Filtra archivos por tags múltiples

docker service inspect tagfs_backend2. **📤 Upload Zone**: Drag & drop o click para subir

3. **🏷️ Tags Populares**: Click para filtrar rápidamente

# Ver nodos4. **📊 Estadísticas**: Vista en tiempo real del sistema

docker node ls5. **🗂️ Grid de Archivos**: Tarjetas con preview, tags y acciones

6. **✏️ Edición Inline**: Modifica tags sin recargar

# Forzar redistribución7. **🎨 Diseño Responsive**: Funciona en móvil, tablet y desktop

docker service update --force tagfs_backend

```### Capturas de Pantalla:



---```

┌─────────────────────────────────────────────────────┐

## 🎓 Para Presentación al Profesor│  🏷️ Tag-Based File System                          │

│  Organiza tus archivos con etiquetas inteligentes   │

**Puntos clave a defender:**├─────────────────────────────────────────────────────┤

│  📊 10 Archivos  │  🏷️ 15 Tags  │  💾 2.05 MB      │

1. **¿Por qué NO DHT?**├─────────────────────────────────────────────────────┤

   - Complejidad innecesaria para 2-3 nodos│  🔍 [Buscar por tags...]        [📤 Subir archivo] │

   - Consistencia fuerte vs. eventual│  Tags: [trabajo (5)] [importante (3)] [pdf (2)]     │

   - Todos los backends acceden a todos los datos├─────────────────────────────────────────────────────┤

│  📄 documento.pdf    🖼️ foto.jpg    📊 datos.xlsx  │

2. **Tolerancia a fallos:**│  [trabajo] [pdf]     [personal]      [trabajo]      │

   - Réplicas automáticas (Docker Swarm)│  ⬇️ ✏️ 🗑️            ⬇️ ✏️ 🗑️         ⬇️ ✏️ 🗑️       │

   - Datos persistentes en NFS└─────────────────────────────────────────────────────┘

   - Reconexión automática```



3. **Distribución real:**---

   - Frontends stateless (2+)

   - Backends stateless (3+)## 🧪 Testing

   - Almacenamiento compartido

```powershell

📖 **Guía completa:** [`DEFENSA_PROYECTO.md`](DEFENSA_PROYECTO.md)# Ejecutar todos los tests

pytest tests

---

# Con verbose

## 🤝 Contribucionespytest tests -v



Este proyecto es parte de un trabajo universitario sobre Sistemas Distribuidos.# Con cobertura

pytest tests --cov=tags

---```



## 📄 Licencia---



Ver archivo [LICENSE](LICENSE)## 💻 CLI Original (Legacy)



---El proyecto mantiene la CLI original para compatibilidad:



## 🆘 Soporte```powershell

# Modo interactivo

Para dudas o problemas:python main.py

1. Revisa [`INDICE_DOCUMENTACION.md`](INDICE_DOCUMENTACION.md)

2. Ejecuta `bash validate_setup.sh`# Modo no interactivo

3. Consulta logs: `docker service logs -f tagfs_backend`python main.py add "C:\path\archivo.txt" "importante,proyecto"

```

---

**Comandos CLI**: `add`, `delete`, `list`, `add-tags`, `delete-tags`, `show`, `exit`

**Desarrollado para el curso de Sistemas Distribuidos**

---

✅ Sin DHT | ✅ Alta Disponibilidad | ✅ Tolerancia a Fallos

## 🛠️ Tecnologías Utilizadas

### Backend:
- **Python 3.10+**
- **FastAPI** - Framework web moderno y rápido
- **Uvicorn** - Servidor ASGI
- **Pydantic** - Validación de datos
- **Python-multipart** - Para upload de archivos

### Frontend:
- **HTML5 + CSS3 + Vanilla JavaScript**
- **Sin frameworks** - Ligero y rápido
- **Responsive Design**
- **Drag & Drop API**
- **Fetch API** para comunicación con backend

### Storage:
- **Sistema de archivos** para binarios
- **JSON** para metadata (tags)

---

## 📝 Ejemplos de Uso

### Ejemplo 1: Subir archivo con Python
```python
import requests

url = "http://localhost:8000/files"
files = {"file": open("documento.pdf", "rb")}
data = {"tags": "trabajo,importante,pdf"}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### Ejemplo 2: Buscar archivos con curl
```bash
# Todos los archivos
curl http://localhost:8000/files

# Filtrar por tags
curl "http://localhost:8000/files?tags=trabajo,importante"

# Estadísticas
curl http://localhost:8000/stats
```

### Ejemplo 3: Actualizar tags con JavaScript
```javascript
const response = await fetch('http://localhost:8000/files/documento.pdf/tags', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tags: ['nuevo', 'actualizado'] })
});
```

---

## 🔧 Configuración

Puedes modificar el directorio de datos editando `tags/config.py`:

```python
from pathlib import Path

DATA_DIR = Path("./tags_data")        # Directorio base
FILES_DIRNAME = "files"               # Carpeta de archivos
META_FILENAME = "files.json"          # Archivo de metadata
```

O pasar un directorio personalizado:

```python
from tags.core.tag_service import TagService

service = TagService(data_dir="./mi_directorio")
```

---

## 🚀 Roadmap Futuro

- [ ] 🔐 Autenticación y usuarios múltiples
- [ ] ☁️ Integración con cloud storage (S3, Google Drive)
- [ ] 🔄 Sincronización en tiempo real (WebSockets)
- [ ] 🤖 Auto-tagging con ML (reconocimiento de imágenes/texto)
- [ ] 📱 App móvil (React Native)
- [ ] 🔍 Búsqueda full-text en contenido de archivos
- [ ] 🎨 Temas personalizables (dark mode)
- [ ] 📦 Versionado de archivos
- [ ] 🔗 Compartir archivos con links públicos
- [ ] 📊 Dashboard de analytics avanzado

---

 

## 📄 Licencia

Este proyecto está bajo la licencia que se encuentra en el archivo `LICENSE`.

---

## 👨‍💻 Autores

**GAlonso46**
- GitHub: [@GAlonso46](https://github.com/GAlonso46)
**mcampver**
- GitHub: [@mcampver](https://github.com/mcampver)

---

## 🙏 Agradecimientos

Proyecto desarrollado para la materia de Sistemas Distribuidos (4to año).

---

¡Disfruta organizando tus archivos con tags! 🎉
