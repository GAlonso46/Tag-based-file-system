"""
FastAPI REST API - Sistema de archivos con PostgreSQL
Sin FileStore - Solo base de datos
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import json
from pathlib import Path
from sqlalchemy.orm import Session

from .database import engine, Base, get_db
from .models import User, FileDB
from . import auth
from .dependencies import get_current_active_user

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Tag-Based File System API",
    description="PostgreSQL only - sin FileStore",
    version="3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

FILES_DIR = Path("/app/tags_data/files")
FILES_DIR.mkdir(parents=True, exist_ok=True)

class FileInfo(BaseModel):
    name: str
    tags: List[str]
    size: Optional[int] = None

class TagsUpdate(BaseModel):
    tags: List[str]
    version: Optional[int] = None  # Versión actual para optimistic locking

@app.get("/")
async def root():
    return {"status": "online", "version": "3.0", "storage": "PostgreSQL"}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        content = await file.read()
        filename = file.filename
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
        file_path = FILES_DIR / filename
        file_path.write_bytes(content)
        
        file_db = FileDB(
            filename=filename,
            original_filename=filename,
            owner_id=current_user.id,
            tags=json.dumps(tag_list),
            size=len(content),
            mime_type=file.content_type or "application/octet-stream"
        )
        db.add(file_db)
        db.commit()
        db.flush()
        db.refresh(file_db)
        
        return {
            "message": "Archivo subido",
            "filename": filename,
            "tags": tag_list,
            "size": len(content),
            "version": file_db.version
        }
    except Exception as e:
        db.rollback()
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))

def check_file_ownership(db: Session, filename: str, user: User) -> FileDB:
    file_db = db.query(FileDB).filter(FileDB.filename == filename).first()
    if not file_db:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if user.is_admin == 1:
        return file_db
    if file_db.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Sin permiso")
    return file_db

@app.get("/download/{filename}")
async def download_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file_db = check_file_ownership(db, filename, current_user)
    file_path = FILES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado")
    return FileResponse(path=str(file_path), filename=filename, media_type=file_db.mime_type)

@app.get("/files")
async def list_files(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.is_admin == 1:
        files = db.query(FileDB).all()
    else:
        files = db.query(FileDB).filter(FileDB.owner_id == current_user.id).all()
    
    return [
        {
            "filename": f.filename,
            "original_filename": f.original_filename,
            "tags": json.loads(f.tags) if f.tags else [],
            "size": f.size,
            "mime_type": f.mime_type,
            "owner_id": f.owner_id,
            "version": f.version,
            "created_at": f.created_at.isoformat() if f.created_at else None
        }
        for f in files
    ]

@app.get("/search")
async def search_by_tags(
    tags: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    search_tags = [t.strip().lower() for t in tags.split(",") if t.strip()]
    if not search_tags:
        raise HTTPException(status_code=400, detail="Proporciona al menos un tag")
    
    if current_user.is_admin == 1:
        all_files = db.query(FileDB).all()
    else:
        all_files = db.query(FileDB).filter(FileDB.owner_id == current_user.id).all()
    
    results = []
    for file_db in all_files:
        file_tags = json.loads(file_db.tags) if file_db.tags else []
        file_tags_lower = [t.lower() for t in file_tags]
        if any(tag in file_tags_lower for tag in search_tags):
            results.append({
                "filename": file_db.filename,
                "original_filename": file_db.original_filename,
                "tags": file_tags,
                "size": file_db.size,
                "mime_type": file_db.mime_type,
                "owner_id": file_db.owner_id,
                "version": file_db.version
            })
    return results

@app.put("/files/{filename}/tags")
async def update_tags(
    filename: str,
    tags_update: TagsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar tags con optimistic locking.
    Si se proporciona 'version', valida que coincida antes de actualizar.
    Retorna 409 Conflict si otro usuario modificó el archivo.
    """
    try:
        file_db = check_file_ownership(db, filename, current_user)
        
        # Optimistic locking: validar versión si se proporciona
        if tags_update.version is not None:
            if file_db.version != tags_update.version:
                # Conflicto detectado
                current_tags = json.loads(file_db.tags) if file_db.tags else []
                raise HTTPException(
                    status_code=409,
                    detail=f"Conflict: versión esperada {tags_update.version}, actual {file_db.version}"
                )
        
        # Actualizar tags e incrementar versión
        file_db.tags = json.dumps(tags_update.tags)
        file_db.version += 1
        db.commit()
        db.flush()
        db.refresh(file_db)
        
        return {
            "message": "Tags actualizados",
            "filename": filename,
            "tags": tags_update.tags,
            "version": file_db.version
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/{filename}")
async def delete_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file_db = check_file_ownership(db, filename, current_user)
    db.delete(file_db)
    db.commit()
    db.flush()
    
    file_path = FILES_DIR / filename
    if file_path.exists():
        file_path.unlink()
    
    return {"message": "Archivo eliminado", "filename": filename}

@app.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.is_admin == 1:
        total_files = db.query(FileDB).count()
        total_users = db.query(User).count()
    else:
        total_files = db.query(FileDB).filter(FileDB.owner_id == current_user.id).count()
        total_users = 1
    
    return {
        "total_files": total_files,
        "total_users": total_users,
        "storage": "PostgreSQL",
        "version": "3.0"
    }
