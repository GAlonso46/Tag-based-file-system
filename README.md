# 🏷️ Tag-Based File System

Sistema de gestión de archivos basado en etiquetas con interfaz web moderna y API REST.

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)

## 📋 Características

- ✅ **Subir archivos** con drag & drop
- 🔍 **Búsqueda inteligente** por múltiples tags (operador AND)
- 🏷️ **Gestión de etiquetas** flexible (añadir, eliminar, editar)
- 📊 **Estadísticas en tiempo real** (archivos, tags, espacio usado)
- 🎨 **Interfaz moderna** tipo Google Drive/Pinterest
- 🚀 **API REST completa** con documentación automática
- 💾 **Persistencia local** con JSON y sistema de archivos

---

## 🚀 Inicio Rápido

### Opción A: Script Automático (Más Fácil) ⭐

```powershell
# 1. Instalar dependencias (solo la primera vez)
pip install -r requirements.txt

# 2. Ejecutar todo con un solo comando
.\start.ps1
```

¡Eso es todo! El script:
- ✅ Inicia la API en una nueva ventana
- ✅ Espera a que esté lista
- ✅ Abre el frontend automáticamente

### Opción B: Manual (Más Control)

**⚠️ IMPORTANTE: Necesitas 2 terminales separadas**

#### Terminal 1 - API (dejar abierta)
```powershell
# 1. Instalar dependencias (solo la primera vez)
pip install -r requirements.txt

# 2. Iniciar servidor API
python run_api.py

# ¡NO CIERRES ESTA TERMINAL!
```

La API estará disponible en:
- 🌐 **API**: http://localhost:8000
- 📚 **Documentación interactiva**: http://localhost:8000/docs
- 📖 **Documentación alternativa**: http://localhost:8000/redoc

#### Terminal 2 - Frontend (nueva terminal)
```powershell
# En una NUEVA terminal de PowerShell
start frontend\index.html
```

> 💡 **Tip**: Usa VS Code y abre 2 terminales integradas (botón "+" en el panel de terminales)

---

## 📁 Estructura del Proyecto

```
Tag-based-file-system/
├── 🎨 frontend/
│   └── index.html              # Interfaz web completa (single-page)
│
├── 🔧 api/
│   ├── __init__.py
│   └── main.py                 # API REST con FastAPI
│
├── 📦 tags/
│   ├── cli/
│   │   ├── __init__.py
│   │   └── app.py              # CLI original (legacy)
│   ├── core/
│   │   ├── __init__.py
│   │   └── tag_service.py      # Lógica de negocio
│   ├── data/
│   │   ├── __init__.py
│   │   └── file_store.py       # Capa de persistencia
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py          # Utilidades
│   └── config.py               # Configuración
│
├── 📂 tags_data/
│   └── files/
│       ├── files.json          # Metadata (tags por archivo)
│       └── [archivos subidos]  # Archivos binarios
│
├── 🧪 tests/
│   └── test_db.py              # Tests unitarios
│
├── main.py                     # CLI legacy
├── run_api.py                  # Script para ejecutar la API
├── requirements.txt            # Dependencias
└── README.md                   # Este archivo
```

---

## 🎯 Endpoints de la API

### 📤 Subir Archivo
```http
POST /files
Content-Type: multipart/form-data

file: <archivo>
tags: "trabajo,importante,pdf"
```

### 📋 Listar Archivos
```http
GET /files
GET /files?tags=trabajo,importante  # Filtrar por tags
```

### ⬇️ Descargar Archivo
```http
GET /files/{filename}
```

### 🗑️ Eliminar Archivo
```http
DELETE /files/{filename}
```

### ✏️ Actualizar Tags (reemplazar)
```http
PATCH /files/{filename}/tags
Content-Type: application/json

{
  "tags": ["nuevo", "tags"]
}
```

### ➕ Añadir Tags (sin eliminar existentes)
```http
POST /files/{filename}/tags
Content-Type: application/json

{
  "tags": ["extra", "tags"]
}
```

### ➖ Eliminar Tags Específicos
```http
DELETE /files/{filename}/tags
Content-Type: application/json

{
  "tags": ["tag_a_eliminar"]
}
```

### 🏷️ Obtener Todos los Tags
```http
GET /tags

# Respuesta:
{
  "tags": [
    {"name": "trabajo", "count": 5},
    {"name": "importante", "count": 3}
  ],
  "total": 2
}
```

### 📊 Estadísticas
```http
GET /stats

# Respuesta:
{
  "total_files": 10,
  "total_tags": 15,
  "total_size_bytes": 2048000,
  "total_size_mb": 2.05
}
```

---

## 🎨 Interfaz Web

### Características de la UI:

1. **🎯 Barra de Búsqueda**: Filtra archivos por tags múltiples
2. **📤 Upload Zone**: Drag & drop o click para subir
3. **🏷️ Tags Populares**: Click para filtrar rápidamente
4. **📊 Estadísticas**: Vista en tiempo real del sistema
5. **🗂️ Grid de Archivos**: Tarjetas con preview, tags y acciones
6. **✏️ Edición Inline**: Modifica tags sin recargar
7. **🎨 Diseño Responsive**: Funciona en móvil, tablet y desktop

### Capturas de Pantalla:

```
┌─────────────────────────────────────────────────────┐
│  🏷️ Tag-Based File System                          │
│  Organiza tus archivos con etiquetas inteligentes   │
├─────────────────────────────────────────────────────┤
│  📊 10 Archivos  │  🏷️ 15 Tags  │  💾 2.05 MB      │
├─────────────────────────────────────────────────────┤
│  🔍 [Buscar por tags...]        [📤 Subir archivo] │
│  Tags: [trabajo (5)] [importante (3)] [pdf (2)]     │
├─────────────────────────────────────────────────────┤
│  📄 documento.pdf    🖼️ foto.jpg    📊 datos.xlsx  │
│  [trabajo] [pdf]     [personal]      [trabajo]      │
│  ⬇️ ✏️ 🗑️            ⬇️ ✏️ 🗑️         ⬇️ ✏️ 🗑️       │
└─────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

```powershell
# Ejecutar todos los tests
pytest tests

# Con verbose
pytest tests -v

# Con cobertura
pytest tests --cov=tags
```

---

## 💻 CLI Original (Legacy)

El proyecto mantiene la CLI original para compatibilidad:

```powershell
# Modo interactivo
python main.py

# Modo no interactivo
python main.py add "C:\path\archivo.txt" "importante,proyecto"
```

**Comandos CLI**: `add`, `delete`, `list`, `add-tags`, `delete-tags`, `show`, `exit`

---

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
