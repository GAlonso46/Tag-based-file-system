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
import grpc
import random
from pathlib import Path

# gRPC protos
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

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

# ==================== METADATA SERVICE CONNECTION ====================

def get_metadata_nodes():
    """Get all IPs for metadata_service from DNS (dynamic discovery)"""
    import socket
    try:
        # Docker's network-alias returns ALL IPs for containers with that alias
        hostname = "metadata_service"
        port = 50051
        # getaddrinfo returns all IPs associated with the hostname
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
        nodes = []
        seen_ips = set()
        for info in addr_info:
            ip = info[4][0]
            if ip not in seen_ips:
                seen_ips.add(ip)
                nodes.append({"host": ip, "port": port})
        return nodes if nodes else [{"host": "metadata_1", "port": 50051}]
    except Exception as e:
        print(f"DNS lookup failed: {e}, using fallback", flush=True)
        # Fallback to environment variable
        nodes_str = os.getenv("METADATA_NODES", "metadata_1:50051")
        nodes = []
        for node in nodes_str.split(","):
            parts = node.strip().split(":")
            if len(parts) == 2:
                nodes.append({"host": parts[0], "port": int(parts[1])})
        return nodes

def get_datanode_nodes():
    """Get all IPs for datanode_service from DNS (dynamic discovery)"""
    import socket
    try:
        hostname = "datanode_service"
        port = 50052
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
        nodes = []
        seen_ips = set()
        for info in addr_info:
            ip = info[4][0]
            if ip not in seen_ips:
                seen_ips.add(ip)
                nodes.append({"host": ip, "port": port})
        return nodes if nodes else [{"host": "datanode_1", "port": 50052}]
    except Exception as e:
        print(f"DNS lookup failed: {e}, using fallback", flush=True)
        nodes_str = os.getenv("DATANODE_NODES", "datanode_1:50052")
        nodes = []
        for node in nodes_str.split(","):
            parts = node.strip().split(":")
            if len(parts) == 2:
                nodes.append({"host": parts[0], "port": int(parts[1])})
        return nodes

def new_metadata_stub():
    """Create a new ephemeral metadata stub (DNS round-robin each time)"""
    nodes = get_metadata_nodes()
    node = random.choice(nodes)
    
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ]
    
    channel = grpc.insecure_channel(
        f"{node['host']}:{node['port']}",
        options=options
    )
    
    return pb2_grpc.MetadataServiceStub(channel), channel

def get_datanode_stub(node_host_port):
    """Get datanode stub for specific node"""
    channel = grpc.insecure_channel(node_host_port)
    return pb2_grpc.DataNodeServiceStub(channel)

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
    
    # If file not in local DB, try to sync from metadata service
    if not file_db:
        try:
            stub, channel = new_metadata_stub()
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
            
            for f in response.files:
                if f.metadata.filename == filename:
                    # Create DB entry for this file
                    import json
                    file_db = FileDB(
                        filename=filename,
                        original_filename=filename,
                        owner_id=int(f.metadata.owner_id),
                        tags=json.dumps(list(f.metadata.tags)),
                        size=f.metadata.size,
                        mime_type=f.metadata.mime_type
                    )
                    db.add(file_db)
                    db.commit()
                    db.refresh(file_db)
                    break
            channel.close()
        except Exception as e:
            print(f"Error syncing file from metadata: {e}", flush=True)
    
    if not file_db:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
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
        filename = file.filename
        file_size = len(content)
        
        # Normalizar tags
        if tags:
            normalized_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        else:
            normalized_tags = []
        
        # 1. Request write allocation from metadata service
        stub, channel = new_metadata_stub()
        try:
            write_request = pb2.WriteRequest(
                filename=filename,
                size=file_size,
                tags=normalized_tags,
                owner_id=str(current_user.id),
                mime_type=file.content_type or "application/octet-stream"
            )
            allocation = stub.AssignWrite(write_request, timeout=5.0)
        finally:
            channel.close()
        
        file_id = allocation.file_id
        target_nodes = allocation.target_nodes
        
        # 2. Upload chunks to assigned datanodes
        successful_nodes = []
        if target_nodes:
            for node in target_nodes:
                try:
                    node_address = f"{node.address}:{node.port}"
                    datanode_stub = get_datanode_stub(node_address)
                    
                    # Stream chunks to datanode
                    CHUNK_SIZE = 1024 * 1024  # 1MB
                    def chunk_generator():
                        offset = 0
                        while offset < file_size:
                            chunk_data = content[offset:offset + CHUNK_SIZE]
                            is_last = (offset + len(chunk_data)) >= file_size
                            yield pb2.FileChunk(
                                file_id=file_id,
                                content=chunk_data,
                                offset=offset,
                                is_last=is_last
                            )
                            offset += len(chunk_data)
                    
                    store_response = datanode_stub.StoreChunk(chunk_generator(), timeout=30.0)
                    
                    if store_response.success:
                        successful_nodes.append(node.node_id)
                except Exception as e:
                    print(f"Failed to upload to {node.address}:{node.port}: {e}", flush=True)
                    continue
        
        # 3. Commit write to metadata service
        if successful_nodes:
            stub, channel = new_metadata_stub()
            try:
                commit_request = pb2.CommitRequest(
                    file_id=file_id,
                    size=file_size,
                    success=True,
                    successful_nodes=successful_nodes
                )
                commit_response = stub.CommitWrite(commit_request, timeout=5.0)
                
                if not commit_response.success:
                    raise HTTPException(status_code=500, detail=f"Commit failed: {commit_response.message}")
            finally:
                channel.close()
        else:
            raise HTTPException(status_code=500, detail="No datanode accepted the file")
        
        # Registrar en la base de datos local asociado al usuario
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
        # Consultar metadata service via gRPC
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
        finally:
            channel.close()
        
        result = []
        for file_loc in response.files:
            file_meta = file_loc.metadata
            # Filtrar por tags si se especificaron
            if tags:
                requested_tags = set(tag.strip().lower() for tag in tags.split(","))
                file_tags_set = set(tag.lower() for tag in file_meta.tags)
                if not requested_tags.issubset(file_tags_set):
                    continue
            
            # Filtrar por usuario (admin ve todo, usuario normal solo suyos)
            if current_user.is_admin != 1:
                if str(file_meta.owner_id) != str(current_user.id):
                    continue
            
            # Si es admin, incluir información del propietario
            owner_name = None
            if current_user.is_admin == 1:
                file_db = db.query(FileDB).filter(FileDB.filename == file_meta.filename).first()
                if file_db and file_db.owner:
                    owner_name = file_db.owner.username
            
            result.append(FileResponse(
                name=file_meta.filename,
                tags=list(file_meta.tags),
                size=file_meta.size,
                url=f"/files/{file_meta.filename}",
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
    try:
        # Verificar propiedad del archivo en DB local
        check_file_ownership(db, filename, current_user)
        
        # Get file metadata from metadata service
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
        finally:
            channel.close()
        
        file_loc = None
        for f in response.files:
            if f.metadata.filename == filename:
                file_loc = f
                break
        
        if not file_loc or not file_loc.replica_nodes:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        # Download from first available datanode replica
        target_node = file_loc.replica_nodes[0]
        target_datanode = f"{target_node.address}:{target_node.port}"
        datanode_stub = get_datanode_stub(target_datanode)
        
        # Request chunks from datanode
        download_request = pb2.FileRequest(file_id=file_loc.file_id)
        chunks = datanode_stub.RetrieveChunk(download_request, timeout=30.0)
        
        # Collect all chunks
        file_content = b""
        for chunk in chunks:
            file_content += chunk.content
        
        # Return as streaming response
        from fastapi.responses import Response
        return Response(
            content=file_content,
            media_type=file_loc.metadata.mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al descargar archivo: {str(e)}")

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
        
        # Get file_id from metadata service
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
            
            file_id = None
            for f in response.files:
                if f.metadata.filename == filename:
                    file_id = f.file_id
                    break
            
            if not file_id:
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            # Delete via gRPC
            delete_response = stub.DeleteFile(pb2.FileRequest(file_id=file_id), timeout=5.0)
        finally:
            channel.close()
        
        if not delete_response.success:
            raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {delete_response.message}")
        
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
        
        # Get file_id from metadata service
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
            
            file_id = None
            for f in response.files:
                if f.metadata.filename == filename:
                    file_id = f.file_id
                    break
            
            if not file_id:
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            # Update tags via gRPC
            update_request = pb2.UpdateTagsRequest(
                file_id=file_id,
                tags=tags_update.tags
            )
            tag_response = stub.UpdateTags(update_request, timeout=5.0)
        finally:
            channel.close()
        
        if not tag_response.success:
            raise HTTPException(status_code=500, detail="Error al actualizar tags en metadata service")
        
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
async def add_tags_to_file(
    filename: str,
    tags_update: TagsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Añadir tags a un archivo (sin eliminar los existentes)
    
    - **filename**: Nombre del archivo
    - **tags**: Tags a añadir
    """
    try:
        # Verificar propiedad del archivo
        check_file_ownership(db, filename, current_user)
        
        # Get file_id from metadata service
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
            
            file_id = None
            current_tags = []
            for f in response.files:
                if f.metadata.filename == filename:
                    file_id = f.file_id
                    current_tags = list(f.metadata.tags)
                    break
            
            if not file_id:
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            # Add tags via gRPC
            add_request = pb2.TagRequest(
                file_id=file_id,
                tags=tags_update.tags
            )
            tag_response = stub.AddTags(add_request, timeout=5.0)
        finally:
            channel.close()
        
        if not tag_response.success:
            raise HTTPException(status_code=500, detail="Error al añadir tags en metadata service")
        
        return {
            "message": "Tags añadidos correctamente",
            "filename": filename,
            "tags": list(tag_response.current_tags)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al añadir tags: {str(e)}")

@app.delete("/files/{filename}/tags")
async def remove_tags_from_file(
    filename: str,
    tags_update: TagsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Eliminar tags específicos de un archivo
    
    - **filename**: Nombre del archivo
    - **tags**: Tags a eliminar
    """
    try:
        # Verificar propiedad del archivo
        check_file_ownership(db, filename, current_user)
        
        # Get file_id from metadata service
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
            
            file_id = None
            for f in response.files:
                if f.metadata.filename == filename:
                    file_id = f.file_id
                    break
            
            if not file_id:
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            # Remove tags via gRPC
            remove_request = pb2.TagRequest(
                file_id=file_id,
                tags=tags_update.tags
            )
            tag_response = stub.RemoveTags(remove_request, timeout=5.0)
        finally:
            channel.close()
        
        if not tag_response.success:
            raise HTTPException(status_code=500, detail="Error al eliminar tags en metadata service")
        
        return {
            "message": "Tags eliminados correctamente",
            "filename": filename,
            "tags": list(tag_response.current_tags)
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
        # Consultar metadata service via gRPC
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
        finally:
            channel.close()
        
        tag_count = {}
        
        for file_loc in response.files:
            file_meta = file_loc.metadata
            # Filtrar por usuario (admin ve todo, usuario normal solo suyos)
            if current_user.is_admin != 1:
                if str(file_meta.owner_id) != str(current_user.id):
                    continue
            
            for tag in file_meta.tags:
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
        # Consultar metadata service via gRPC
        stub, channel = new_metadata_stub()
        try:
            response = stub.ListFiles(pb2.ListRequest(tags_filter=[], owner_filter=""), timeout=5.0)
        finally:
            channel.close()
        
        total_files = 0
        all_tags = set()
        total_size = 0
        
        for file_loc in response.files:
            file_meta = file_loc.metadata
            # Filtrar por usuario (admin ve todo, usuario normal solo suyos)
            if current_user.is_admin != 1:
                if str(file_meta.owner_id) != str(current_user.id):
                    continue
            
            total_files += 1
            all_tags.update(file_meta.tags)
            total_size += file_meta.size
        
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
