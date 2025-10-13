"""
FastAPI REST API para el sistema de archivos basado en tags
Con autenticación JWT
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import os
from pathlib import Path

from tags.core.tag_service import TagService
from tags.utils.helpers import normalize_tags

# Importar módulos de autenticación
from sqlalchemy.orm import Session
from .database import engine, Base, get_db
from .models import User, FileDB
from . import auth
from .dependencies import get_current_active_user

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

# Inicializar FastAPI
app = FastAPI(
    title="Tag-Based File System API",
    description="API REST para gestionar archivos con sistema de etiquetas y autenticación JWT",
    version="2.0.0"
)

# Configurar CORS para permitir requests desde cualquier origen (desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes (incluyendo file://)
    allow_credentials=False,  # Debe ser False cuando allow_origins es "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir router de autenticación
app.include_router(auth.router)

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
    owner: Optional[str] = None  # Nombre del propietario (solo visible para admins)

# ==================== FUNCIONES AUXILIARES ====================

def get_or_create_file_in_db(db: Session, filename: str, owner_id: int, tags: List[str], size: int, mime_type: str) -> FileDB:
    """Obtiene o crea un registro de archivo en la BD"""
    import json
    file_db = db.query(FileDB).filter(FileDB.filename == filename).first()
    
    if not file_db:
        file_db = FileDB(
            filename=filename,
            original_filename=filename,
            owner_id=owner_id,
            tags=json.dumps(tags),
            size=size,
            mime_type=mime_type
        )
        db.add(file_db)
        db.commit()
        db.refresh(file_db)
    
    return file_db

def check_file_ownership(db: Session, filename: str, user: User) -> FileDB:
    """Verifica que el usuario sea dueño del archivo o admin"""
    file_db = db.query(FileDB).filter(FileDB.filename == filename).first()
    
    if not file_db:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la base de datos")
    
    # Si es admin, puede acceder a cualquier archivo
    if user.is_admin == 1:
        return file_db
    
    # Si no es admin, solo puede acceder a sus propios archivos
    if file_db.owner_id != user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para acceder a este archivo")
    
    return file_db

def filter_files_by_user(files_with_tags: List[tuple], db: Session, user: User) -> List[tuple]:
    """Filtra archivos según el usuario (admin ve todo, usuario normal solo los suyos)"""
    if user.is_admin == 1:
        return files_with_tags
    
    # Usuario normal: filtrar solo sus archivos
    user_files = []
    for filename, tags in files_with_tags:
        file_db = db.query(FileDB).filter(FileDB.filename == filename).first()
        if file_db and file_db.owner_id == user.id:
            user_files.append((filename, tags))
    
    return user_files

# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Tag-Based File System API"}

@app.post("/files", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(default=""),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Subir un archivo con tags opcionales (requiere autenticación)
    
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
        
        # Registrar en la base de datos asociado al usuario
        get_or_create_file_in_db(
            db=db,
            filename=filename,
            owner_id=current_user.id,
            tags=normalized_tags,
            size=file_size,
            mime_type=file.content_type or "application/octet-stream"
        )
        
        return FileResponse(
            name=filename,
            tags=normalized_tags,
            size=file_size,
            url=f"/files/{filename}"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

@app.get("/files", response_model=List[FileResponse])
async def list_files(
    tags: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Listar archivos del usuario (o todos si es admin), opcionalmente filtrados por tags
    
    - **tags**: Tags para filtrar, separados por comas (AND logic)
    """
    try:
        if tags:
            # Filtrar por tags
            files_with_tags = tag_service.list_by_tags(tags)
        else:
            # Mostrar todos
            files_with_tags = tag_service.show_all()
        
        # Filtrar archivos según el usuario (admin ve todo, usuario normal solo los suyos)
        filtered_files = filter_files_by_user(files_with_tags, db, current_user)
        
        result = []
        files_dir = Path(DATA_DIR) / "files"
        
        for filename, file_tags in filtered_files:
            file_path = files_dir / filename
            if file_path.exists():
                # Si es admin, incluir información del propietario
                owner_name = None
                if current_user.is_admin == 1:
                    file_db = db.query(FileDB).filter(FileDB.filename == filename).first()
                    if file_db and file_db.owner:
                        owner_name = file_db.owner.username
                
                result.append(FileResponse(
                    name=filename,
                    tags=file_tags,
                    size=file_path.stat().st_size,
                    url=f"/files/{filename}",
                    owner=owner_name
                ))
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")

@app.get("/files/{filename}")
async def download_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Descargar un archivo específico (requiere autenticación y propiedad/admin)
    
    - **filename**: Nombre del archivo
    """
    # Verificar propiedad del archivo
    check_file_ownership(db, filename, current_user)
    
    file_path = Path(DATA_DIR) / "files" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.delete("/files/{filename}")
async def delete_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Eliminar un archivo (requiere autenticación y propiedad/admin)
    
    - **filename**: Nombre del archivo a eliminar
    """
    try:
        # Verificar propiedad del archivo
        file_db = check_file_ownership(db, filename, current_user)
        
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
        
        # Eliminar de la base de datos
        db.delete(file_db)
        db.commit()
        
        return {"message": f"Archivo '{filename}' eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {str(e)}")

@app.patch("/files/{filename}/tags")
async def update_file_tags(
    filename: str,
    tags_update: TagsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar los tags de un archivo (reemplaza los tags existentes, requiere propiedad/admin)
    
    - **filename**: Nombre del archivo
    - **tags**: Nueva lista de tags
    """
    try:
        # Verificar propiedad del archivo
        file_db = check_file_ownership(db, filename, current_user)
        
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
        
        # Actualizar tags en la base de datos
        import json
        file_db.tags = json.dumps(tags_update.tags)
        db.commit()
        
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
async def get_all_tags(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtener todos los tags únicos (admin: todos, usuario: solo de sus archivos)
    """
    try:
        files_with_tags = tag_service.show_all()
        
        # Filtrar archivos según usuario
        filtered_files = filter_files_by_user(files_with_tags, db, current_user)
        
        tag_count = {}
        
        for _, tags in filtered_files:
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
async def get_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtener estadísticas (admin: globales, usuario: personales)
    """
    try:
        files_with_tags = list(tag_service.show_all())
        
        # Filtrar archivos según usuario
        filtered_files = filter_files_by_user(files_with_tags, db, current_user)
        
        total_files = len(filtered_files)
        all_tags = set()
        files_dir = Path(DATA_DIR) / "files"
        total_size = 0
        
        for filename, tags in filtered_files:
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

# ==================== ANALYTICS ENDPOINTS (SOLO ADMIN) ====================

@app.get("/analytics/files-by-date")
async def analytics_files_by_date(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Archivos subidos por día en los últimos N días (Solo Admin)
    """
    if current_user.is_admin != 1:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a analytics")
    
    try:
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        # Calcular fecha de inicio
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Obtener archivos de la BD
        files = db.query(FileDB).filter(FileDB.created_at >= start_date).all()
        
        # Agrupar por fecha
        files_by_date = defaultdict(int)
        for file in files:
            date_key = file.created_at.strftime("%Y-%m-%d")
            files_by_date[date_key] += 1
        
        # Generar todas las fechas en el rango
        labels = []
        data = []
        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.strftime("%Y-%m-%d")
            labels.append(date_key)
            data.append(files_by_date.get(date_key, 0))
            current_date += timedelta(days=1)
        
        return {
            "labels": labels,
            "data": data,
            "total": sum(data)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener analytics: {str(e)}")

@app.get("/analytics/files-by-type")
async def analytics_files_by_type(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Distribución de archivos por tipo MIME (Solo Admin)
    """
    if current_user.is_admin != 1:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a analytics")
    
    try:
        from collections import defaultdict
        
        files = db.query(FileDB).all()
        
        # Agrupar por tipo
        type_count = defaultdict(int)
        for file in files:
            # Simplificar tipo MIME
            mime_type = file.mime_type or "application/octet-stream"
            if mime_type.startswith("image/"):
                category = "Imágenes"
            elif mime_type.startswith("video/"):
                category = "Videos"
            elif mime_type == "application/pdf":
                category = "PDFs"
            elif mime_type.startswith("text/"):
                category = "Texto"
            elif mime_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                category = "Documentos"
            elif mime_type in ["application/zip", "application/x-rar-compressed"]:
                category = "Archivos"
            else:
                category = "Otros"
            
            type_count[category] += 1
        
        return {
            "labels": list(type_count.keys()),
            "data": list(type_count.values())
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener analytics: {str(e)}")

@app.get("/analytics/tags-usage")
async def analytics_tags_usage(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Top 10 tags más usados con timeline (Solo Admin)
    """
    if current_user.is_admin != 1:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a analytics")
    
    try:
        import json
        from collections import defaultdict
        
        files = db.query(FileDB).all()
        
        # Contar tags
        tag_count = defaultdict(int)
        for file in files:
            if file.tags:
                tags = json.loads(file.tags)
                for tag in tags:
                    tag_count[tag] += 1
        
        # Top 10
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "labels": [tag for tag, _ in sorted_tags],
            "data": [count for _, count in sorted_tags]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener analytics: {str(e)}")

@app.get("/analytics/storage-by-tag")
async def analytics_storage_by_tag(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Espacio usado por cada tag (Solo Admin)
    """
    if current_user.is_admin != 1:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a analytics")
    
    try:
        import json
        from collections import defaultdict
        
        files = db.query(FileDB).all()
        
        # Sumar tamaño por tag
        tag_size = defaultdict(int)
        for file in files:
            if file.tags:
                tags = json.loads(file.tags)
                for tag in tags:
                    tag_size[tag] += file.size
        
        # Ordenar por tamaño
        sorted_tags = sorted(tag_size.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "labels": [tag for tag, _ in sorted_tags],
            "data": [round(size / (1024 * 1024), 2) for _, size in sorted_tags],  # En MB
            "unit": "MB"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener analytics: {str(e)}")

@app.get("/analytics/user-stats")
async def analytics_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Estadísticas por usuario (Solo Admin)
    """
    if current_user.is_admin != 1:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a analytics")
    
    try:
        users = db.query(User).all()
        
        stats = []
        for user in users:
            file_count = len(user.files)
            total_size = sum(file.size for file in user.files)
            
            stats.append({
                "username": user.username,
                "email": user.email,
                "is_admin": user.is_admin == 1,
                "file_count": file_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            })
        
        return {
            "users": stats,
            "total_users": len(users)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener analytics: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
