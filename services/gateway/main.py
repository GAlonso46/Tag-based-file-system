import os
import io
import grpc
import json
import asyncio
import concurrent.futures
from concurrent import futures
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import Response, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.orm import Session

# Distributed components
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc
from tags.utils.helpers import normalize_tags
from api import auth
from api.dependencies import get_current_active_user
from api.models import User
from api.database import get_db

# Configuration
METADATA_HOST = os.getenv("METADATA_HOST", "metadata")
METADATA_PORT = os.getenv("METADATA_PORT", "50051")
CHUNK_SIZE = 1024 * 1024
ENABLE_TLS = os.getenv("ENABLE_TLS", "false").lower() == "true"
CERT_DIR = os.getenv("CERT_DIR", "./certs")

app = FastAPI(title="TagFS Gateway", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

from api.database import engine, Base
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


# gRPC Clients - no longer maintaining persistent connections

def get_grpc_credentials():
    """Get gRPC credentials (TLS or insecure)"""
    if not ENABLE_TLS:
        return None
    
    try:
        with open(f"{CERT_DIR}/ca-cert.pem", "rb") as f:
            root_cert = f.read()
        with open(f"{CERT_DIR}/client-cert.pem", "rb") as f:
            client_cert = f.read()
        with open(f"{CERT_DIR}/client-key.pem", "rb") as f:
            client_key = f.read()
        
        credentials = grpc.ssl_channel_credentials(
            root_certificates=root_cert,
            private_key=client_key,
            certificate_chain=client_cert
        )
        print("[Gateway] TLS enabled for gRPC connections", flush=True)
        return credentials
    except Exception as e:
        print(f"[Gateway] Warning: Could not load TLS certificates: {e}", flush=True)
        print("[Gateway] Falling back to insecure connections", flush=True)
        return None

def new_metadata_stub():
    """Create a new ephemeral metadata stub (DNS round-robin each time)"""
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ]
    
    credentials = get_grpc_credentials()
    if credentials:
        channel = grpc.secure_channel(
            f'{METADATA_HOST}:{METADATA_PORT}',
            credentials,
            options=options
        )
    else:
        channel = grpc.insecure_channel(
            f'{METADATA_HOST}:{METADATA_PORT}',
            options=options
        )
    
    return pb2_grpc.MetadataServiceStub(channel), channel

def get_all_metadata_stubs():
    """Get stubs for ALL metadata replicas using round-robin DNS queries"""
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ]
    
    # Expected number of metadata replicas
    EXPECTED_REPLICAS = int(os.getenv("EXPECTED_METADATA_REPLICAS", "3"))
    
    stubs = []
    credentials = get_grpc_credentials()
    
    # Create multiple connections - Docker DNS will round-robin to different IPs
    for i in range(EXPECTED_REPLICAS):
        try:
            if credentials:
                channel = grpc.secure_channel(f'{METADATA_HOST}:{METADATA_PORT}', credentials, options=options)
            else:
                channel = grpc.insecure_channel(f'{METADATA_HOST}:{METADATA_PORT}', options=options)
            stub = pb2_grpc.MetadataServiceStub(channel)
            stubs.append(stub)
        except Exception as e:
            print(f"[Gateway] Failed to connect to metadata replica {i+1}: {e}", flush=True)
    
    print(f"[Gateway] Created {len(stubs)} metadata connections (expecting {EXPECTED_REPLICAS})", flush=True)
    if not stubs:
        stub, channel = new_metadata_stub()
        return [(stub, channel)]
    return stubs



def get_datanode_stub(host, port):
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ]
    
    credentials = get_grpc_credentials()
    if credentials:
        channel = grpc.secure_channel(f'{host}:{port}', credentials, options=options)
    else:
        channel = grpc.insecure_channel(f'{host}:{port}', options=options)
    
    return pb2_grpc.DataNodeServiceStub(channel)

# Generators
def chunk_generator(file_id, content):
    """Yields chunks needed for StoreChunk gRPC call"""
    offset = 0
    chunk_count = 0
    while offset < len(content):
        chunk = content[offset:offset+CHUNK_SIZE]
        chunk_count += 1
        yield pb2.FileChunk(
            file_id=file_id,
            content=chunk,
            offset=offset,
            is_last=(offset + len(chunk) >= len(content))
        )
        offset += len(chunk)
    print(f"[Gateway] Generated {chunk_count} chunks for file {file_id} ({len(content)} bytes total)", flush=True)

# Endpoints

@app.get("/")
def health():
    return {"status": "ok", "role": "gateway"}

@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    tags: str = Form(default=""),
    current_user: User = Depends(get_current_active_user)
):
    try:
        content = await file.read()
        filename = file.filename
        size = len(content)
        normalized_tags = normalize_tags(tags) if tags else []

        meta, channel = new_metadata_stub()

        # Ask Metadata where to put it
        try:
            alloc = meta.AssignWrite(
                pb2.WriteRequest(
                    filename=filename,
                    size=size,
                    tags=normalized_tags,
                    owner_id=str(current_user.id),
                    mime_type=file.content_type
                ),
                timeout=5
            )
        finally:
            channel.close()

        file_id = alloc.file_id
        target_nodes = alloc.target_nodes

        if not target_nodes:
            raise HTTPException(503, "No storage nodes available")

        success_nodes = []

        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=len(target_nodes)
        )

        def upload_to_node(node):
            try:
                ds = get_datanode_stub(node.address, node.port)
                resp = ds.StoreChunk(
                    chunk_generator(file_id, content),
                    timeout=60
                )
                if resp.success:
                    return node.node_id
            except:
                pass
            return None

        tasks = [
            loop.run_in_executor(executor, upload_to_node, node)
            for node in target_nodes
        ]

        results = await asyncio.gather(*tasks)

        success_nodes = [r for r in results if r]

        # AP rule
        if not success_nodes:
            raise HTTPException(
                503, "Could not store file on any DataNode"
            )

        # Commit metadata
        meta, channel = new_metadata_stub()
        try:
            meta.CommitWrite(
                pb2.CommitRequest(
                    file_id=file_id,
                    size=size,
                    success=True,
                    successful_nodes=success_nodes
                ),
                timeout=5
            )
        finally:
            channel.close()

        return {
            "name": filename,
            "tags": list(normalized_tags),
            "size": size,
            "url": f"/files/{file_id}"
        }

    except Exception as e:
        print(e)
        raise HTTPException(500, str(e))


@app.get("/files/{file_id}")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_active_user)
):
    meta, channel = new_metadata_stub()

    try:
        loc = meta.LocateFile(
            pb2.FileRequest(file_id=file_id),
            timeout=5
        )
    finally:
        channel.close()

    if not loc.replica_nodes:
        raise HTTPException(404, "File not found")

    # Try replicas one by one
    for node in loc.replica_nodes:
        try:
            ds = get_datanode_stub(node.address, node.port)
            ds.Ping(pb2.PingRequest(), timeout=2)

            chunks_iter = ds.RetrieveChunk(
                pb2.FileRequest(file_id=file_id),
                timeout=30
            )

            def stream():
                for chunk in chunks_iter:
                    yield chunk.content

            return StreamingResponse(
                stream(),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition":
                    f"attachment; filename={loc.metadata.filename}"
                }
            )

        except Exception as e:
            print(
                f"[Gateway] Replica {node.node_id} failed: {e}",
                flush=True
            )
            continue

    raise HTTPException(503, "No replicas available")


@app.delete("/files/{file_id}")
async def delete_file(file_id: str, current_user: User = Depends(get_current_active_user)):
    """Delete a file (soft delete with tombstone)"""
    try:
        meta, channel = new_metadata_stub()
        
        try:
            # Verify file exists and user has permission
            loc = meta.LocateFile(pb2.FileRequest(file_id=file_id), timeout=5)
            
            # Check ownership (unless admin)
            if current_user.is_admin != 1 and loc.metadata.owner_id != str(current_user.id):
                raise HTTPException(403, "Not authorized to delete this file")
            
            # Mark as deleted in metadata (tombstone)
            result = meta.DeleteFile(pb2.FileRequest(file_id=file_id), timeout=5)
        finally:
            channel.close()
        
        if result.success:
            return {"message": "File deleted successfully", "file_id": file_id}
        else:
            raise HTTPException(500, "Failed to delete file")
            
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(404, "File not found")
        elif e.code() == grpc.StatusCode.UNIMPLEMENTED:
            raise HTTPException(501, "Delete operation not implemented in metadata service")
        raise HTTPException(500, f"RPC Error: {e.details()}")

@app.patch("/files/{file_id}/tags")
async def update_tags(
    file_id: str,
    tags_data: dict,
    current_user: User = Depends(get_current_active_user)
):
    """Update tags for a file"""
    try:
        if "tags" not in tags_data:
            raise HTTPException(400, "Missing 'tags' field in request body")
        
        new_tags = tags_data["tags"]
        if not isinstance(new_tags, list):
            raise HTTPException(400, "'tags' must be an array")
        
        meta, channel = new_metadata_stub()
        
        try:
            # Verify file exists and user has permission
            loc = meta.LocateFile(pb2.FileRequest(file_id=file_id), timeout=5)
            
            # Check ownership (unless admin)
            if current_user.is_admin != 1 and loc.metadata.owner_id != str(current_user.id):
                raise HTTPException(403, "Not authorized to modify this file")
            
            # Update tags
            normalized_tags = normalize_tags(",".join(new_tags)) if new_tags else []
            result = meta.UpdateTags(pb2.UpdateTagsRequest(
                file_id=file_id,
                tags=normalized_tags
            ), timeout=5)
        finally:
            channel.close()
        
        if result.success:
            return {
                "message": "Tags updated successfully",
                "file_id": file_id,
                "tags": normalized_tags
            }
        else:
            raise HTTPException(500, "Failed to update tags")
            
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(404, "File not found")
        elif e.code() == grpc.StatusCode.UNIMPLEMENTED:
            raise HTTPException(501, "UpdateTags operation not implemented in metadata service")
        raise HTTPException(500, f"RPC Error: {e.details()}")

@app.get("/files")
async def list_files(
    tags: Optional[str] = None, 
    current_user: User = Depends(get_current_active_user)
):
    # Query ALL metadata replicas using fresh connections each time
    EXPECTED_REPLICAS = int(os.getenv("EXPECTED_METADATA_REPLICAS", "3"))
    
    req = pb2.ListRequest()
    if tags:
        req.tags_filter.extend(tags.split(","))
    
    # Admin filter: if not admin, filter by owner_id
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    # Collect files from all metadata nodes
    all_files = {}
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
    ]
    
    credentials = get_grpc_credentials()
    
    # Make multiple requests - DNS round-robin will hit different replicas
    for i in range(EXPECTED_REPLICAS):
        try:
            # Create fresh channel for each request to force DNS lookup
            if credentials:
                channel = grpc.insecure_channel(f'{METADATA_HOST}:{METADATA_PORT}', options=options)
            else:
                channel = grpc.insecure_channel(f'{METADATA_HOST}:{METADATA_PORT}', options=options)
            
            stub = pb2_grpc.MetadataServiceStub(channel)
            resp = stub.ListFiles(req, timeout=5)
            
            for f in resp.files:
                # Use file_id as key to deduplicate
                if f.file_id not in all_files:
                    all_files[f.file_id] = {
                        "id": f.file_id,
                        "name": f.metadata.filename,
                        "tags": list(f.metadata.tags),
                        "size": f.metadata.size,
                        "owner_id": f.metadata.owner_id,
                        "url": f"/files/{f.file_id}",
                        "created_at": f.metadata.created_at if hasattr(f.metadata, 'created_at') else ""
                    }
            
            # Close channel after each query to force new DNS lookup
            channel.close()
            
        except Exception as e:
            print(f"[Gateway] Failed to query metadata replica {i+1}: {e}", flush=True)
            continue
    
    print(f"[Gateway] Collected {len(all_files)} unique files from {EXPECTED_REPLICAS} metadata queries", flush=True)
    return list(all_files.values())

@app.get("/tags")
async def get_all_tags(current_user: User = Depends(get_current_active_user)):
    """Get all unique tags from files with count"""
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    # Admin sees all tags, users see only their tags
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Count tags
    tags_count = {}
    for f in resp.files:
        for tag in f.metadata.tags:
            tags_count[tag] = tags_count.get(tag, 0) + 1
    
    # Convertir a formato [{name, count}] ordenado por count descendente
    tags_list = [{"name": tag, "count": count} for tag, count in tags_count.items()]
    tags_list.sort(key=lambda x: x["count"], reverse=True)
    
    return {"tags": tags_list[:10], "total": len(tags_count)}

@app.get("/stats")
async def get_stats(current_user: User = Depends(get_current_active_user)):
    """Get statistics about files"""
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    # Admin sees all stats, users see only their stats
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    total_files = len(resp.files)
    total_size = sum(f.metadata.size for f in resp.files)
    
    # Tag frequency
    tag_counts = {}
    for f in resp.files:
        for tag in f.metadata.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    return {
        "total_files": total_files,
        "total_size": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "tag_counts": tag_counts,
        "is_admin": current_user.is_admin == 1
    }

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/analytics/files-by-date")
async def get_files_by_date(days: int = 30, current_user: User = Depends(get_current_active_user)):
    """Get files grouped by creation date"""
    from datetime import datetime, timedelta
    
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Group by date
    cutoff_date = datetime.now() - timedelta(days=days)
    files_by_date = {}
    total = 0
    
    for f in resp.files:
        if f.metadata.created_at > 0:
            file_date = datetime.fromtimestamp(f.metadata.created_at).strftime('%Y-%m-%d')
            files_by_date[file_date] = files_by_date.get(file_date, 0) + 1
            total += 1
    
    sorted_dates = sorted(files_by_date.items())
    return {
        "labels": [k for k, v in sorted_dates],
        "data": [v for k, v in sorted_dates],
        "total": total
    }

@app.get("/analytics/files-by-type")
async def get_files_by_type(current_user: User = Depends(get_current_active_user)):
    """Get files grouped by MIME type"""
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Group by type
    types_count = {}
    for f in resp.files:
        mime_type = f.metadata.mime_type or 'unknown'
        # Simplify to main category
        main_type = mime_type.split('/')[0] if '/' in mime_type else mime_type
        types_count[main_type] = types_count.get(main_type, 0) + 1
    
    return {
        "labels": list(types_count.keys()),
        "data": list(types_count.values())
    }

@app.get("/analytics/tags-usage")
async def get_tags_usage(current_user: User = Depends(get_current_active_user)):
    """Get most used tags"""
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Count tags
    tag_counts = {}
    for f in resp.files:
        for tag in f.metadata.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort by usage
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "labels": [k for k, v in sorted_tags],
        "data": [v for k, v in sorted_tags]
    }

@app.get("/analytics/storage-by-tag")
async def get_storage_by_tag(current_user: User = Depends(get_current_active_user)):
    """Get storage usage by tag"""
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Storage by tag
    storage_by_tag = {}
    for f in resp.files:
        for tag in f.metadata.tags:
            storage_by_tag[tag] = storage_by_tag.get(tag, 0) + f.metadata.size
    
    # Sort by size
    sorted_storage = sorted(storage_by_tag.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "labels": [k for k, v in sorted_storage],
        "data": [round(v / (1024 * 1024), 2) for k, v in sorted_storage]  # Convert to MB
    }

@app.get("/analytics/user-stats")
async def get_user_stats(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get statistics by user (admin only)"""
    if current_user.is_admin != 1:
        return {"users": [], "total_users": 0}
    
    meta, channel = new_metadata_stub()
    req = pb2.ListRequest()
    try:
        resp = meta.ListFiles(req, timeout=5)
    finally:
        channel.close()
    
    # Stats by owner ID
    user_stats = {}
    for f in resp.files:
        owner_id = f.metadata.owner_id or 'unknown'
        if owner_id not in user_stats:
            user_stats[owner_id] = {"files": 0, "size": 0}
        user_stats[owner_id]["files"] += 1
        user_stats[owner_id]["size"] += f.metadata.size
    
    # Get user info from database
    users_data = []
    for user_id, stats in user_stats.items():
        if user_id == 'unknown':
            users_data.append({
                "username": "unknown",
                "email": "unknown",
                "is_admin": False,
                "file_count": stats["files"],
                "total_size_mb": round(stats["size"] / (1024 * 1024), 2)
            })
        else:
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    users_data.append({
                        "username": user.username,
                        "email": user.email,
                        "is_admin": user.is_admin == 1,
                        "file_count": stats["files"],
                        "total_size_mb": round(stats["size"] / (1024 * 1024), 2)
                    })
            except (ValueError, AttributeError):
                continue
    
    return {
        "users": users_data,
        "total_users": len(users_data)
    }


