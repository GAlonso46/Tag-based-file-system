"""
FastAPI REST API para el sistema de archivos basado en tags
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import os
from pathlib import Path

from tags.core.tag_service import TagService
from tags.utils.helpers import normalize_tags

# Inicializar FastAPI
app = FastAPI(
    title="Tag-Based File System API",
    description="API REST para gestionar archivos con sistema de etiquetas",
    version="1.0.0"
)

# Configurar CORS para permitir requests desde cualquier origen (desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes (incluyendo file://)
    allow_credentials=False,  # Debe ser False cuando allow_origins es "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar el servicio de tags
DATA_DIR = "./tags_data"
tag_service = TagService(DATA_DIR)

# Modelos Pydantic
class FileInfo(BaseModel):
    name: str
    tags: List[str]
    size: Optional[int] = None

class TagsUpdate(BaseModel):
    tags: List[str]

class FileResponse(BaseModel):
    name: str
    tags: List[str]
    size: int
    url: str

# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Tag-Based File System API"}

@app.post("/files", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(default="")
):
    """
    Subir un archivo con tags opcionales
    
    - **file**: Archivo a subir
    - **tags**: Tags separados por comas (ej: "trabajo,importante,pdf")
    """
    try:
        # Leer el contenido del archivo
        content = await file.read()
        
        # Guardar directamente usando FileStore
        filename = file.filename
        tag_service.store.add_file(filename, content)
        
        # Añadir tags si existen
        if tags:
            normalized_tags = normalize_tags(tags)
            tag_service.store.add_tags(filename, normalized_tags)
        else:
            normalized_tags = []
        
        # Obtener el tamaño del archivo
        file_path = Path(DATA_DIR) / "files" / filename
        file_size = file_path.stat().st_size
        
        return FileResponse(
            name=filename,
            tags=normalized_tags,
            size=file_size,
            url=f"/files/{filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

@app.get("/files", response_model=List[FileResponse])
async def list_files(tags: Optional[str] = None):
    """
    Listar archivos, opcionalmente filtrados por tags
    
    - **tags**: Tags para filtrar, separados por comas (AND logic)
    """
    try:
        if tags:
            # Filtrar por tags
            files_with_tags = tag_service.list_by_tags(tags)
        else:
            # Mostrar todos
            files_with_tags = tag_service.show_all()
        
        result = []
        files_dir = Path(DATA_DIR) / "files"
        
        for filename, file_tags in files_with_tags:
            file_path = files_dir / filename
            if file_path.exists():
                result.append(FileResponse(
                    name=filename,
                    tags=file_tags,
                    size=file_path.stat().st_size,
                    url=f"/files/{filename}"
                ))
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")

@app.get("/files/{filename}")
async def download_file(filename: str):
    """
    Descargar un archivo específico
    
    - **filename**: Nombre del archivo
    """
    file_path = Path(DATA_DIR) / "files" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """
    Eliminar un archivo
    
    - **filename**: Nombre del archivo a eliminar
    """
    try:
        # Obtener los tags del archivo para poder eliminarlo
        files_with_tags = tag_service.show_all()
        file_tags = None
        
        for name, tags in files_with_tags:
            if name == filename:
                file_tags = tags
                break
        
        if file_tags is None:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Eliminar usando todos sus tags
        tag_service.delete_by_tags(file_tags)
        
        return {"message": f"Archivo '{filename}' eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {str(e)}")

@app.patch("/files/{filename}/tags")
async def update_file_tags(filename: str, tags_update: TagsUpdate):
    """
    Actualizar los tags de un archivo (reemplaza los tags existentes)
    
    - **filename**: Nombre del archivo
    - **tags**: Nueva lista de tags
    """
    try:
        # Verificar que el archivo existe
        files_with_tags = tag_service.show_all()
        file_exists = any(name == filename for name, _ in files_with_tags)
        
        if not file_exists:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Obtener tags actuales
        current_tags = None
        for name, tags in files_with_tags:
            if name == filename:
                current_tags = tags
                break
        
        # Eliminar tags actuales
        if current_tags:
            tag_service.store.remove_tags(filename, current_tags)
        
        # Añadir nuevos tags
        if tags_update.tags:
            tag_service.store.add_tags(filename, tags_update.tags)
        
        return {
            "message": "Tags actualizados correctamente",
            "filename": filename,
            "tags": tags_update.tags
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar tags: {str(e)}")

@app.post("/files/{filename}/tags")
async def add_tags_to_file(filename: str, tags_update: TagsUpdate):
    """
    Añadir tags a un archivo (sin eliminar los existentes)
    
    - **filename**: Nombre del archivo
    - **tags**: Tags a añadir
    """
    try:
        # Verificar que el archivo existe
        files_with_tags = tag_service.show_all()
        file_exists = any(name == filename for name, _ in files_with_tags)
        
        if not file_exists:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Añadir tags
        tag_service.store.add_tags(filename, tags_update.tags)
        
        # Obtener tags actualizados
        updated_tags = tag_service.store.meta.get(filename, [])
        
        return {
            "message": "Tags añadidos correctamente",
            "filename": filename,
            "tags": list(updated_tags)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al añadir tags: {str(e)}")

@app.delete("/files/{filename}/tags")
async def remove_tags_from_file(filename: str, tags_update: TagsUpdate):
    """
    Eliminar tags específicos de un archivo
    
    - **filename**: Nombre del archivo
    - **tags**: Tags a eliminar
    """
    try:
        # Verificar que el archivo existe
        files_with_tags = tag_service.show_all()
        file_exists = any(name == filename for name, _ in files_with_tags)
        
        if not file_exists:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Eliminar tags
        tag_service.store.remove_tags(filename, tags_update.tags)
        
        # Obtener tags actualizados
        updated_tags = tag_service.store.meta.get(filename, [])
        
        return {
            "message": "Tags eliminados correctamente",
            "filename": filename,
            "tags": list(updated_tags)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar tags: {str(e)}")

@app.get("/tags")
async def get_all_tags():
    """
    Obtener todos los tags únicos del sistema con su frecuencia de uso
    """
    try:
        files_with_tags = tag_service.show_all()
        tag_count = {}
        
        for _, tags in files_with_tags:
            for tag in tags:
                tag_count[tag] = tag_count.get(tag, 0) + 1
        
        # Ordenar por frecuencia descendente
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "tags": [{"name": tag, "count": count} for tag, count in sorted_tags],
            "total": len(sorted_tags)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener tags: {str(e)}")

@app.get("/stats")
async def get_statistics():
    """
    Obtener estadísticas generales del sistema
    """
    try:
        files_with_tags = list(tag_service.show_all())
        
        total_files = len(files_with_tags)
        all_tags = set()
        files_dir = Path(DATA_DIR) / "files"
        total_size = 0
        
        for filename, tags in files_with_tags:
            all_tags.update(tags)
            file_path = files_dir / filename
            if file_path.exists():
                total_size += file_path.stat().st_size
        
        return {
            "total_files": total_files,
            "total_tags": len(all_tags),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
