import os
import io
import grpc
import json
from concurrent import futures
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import Response, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

# Distributed components
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc
from tags.utils.helpers import normalize_tags
from api import auth
from api.dependencies import get_current_active_user
from api.models import User

# Configuration
METADATA_HOST = os.getenv("METADATA_HOST", "metadata")
METADATA_PORT = os.getenv("METADATA_PORT", "50051")
CHUNK_SIZE = 1024 * 1024

app = FastAPI(title="TagFS Gateway", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

# gRPC Clients
def get_metadata_stub():
    channel = grpc.insecure_channel(f'{METADATA_HOST}:{METADATA_PORT}')
    return pb2_grpc.MetadataServiceStub(channel)

def get_datanode_stub(host, port):
    channel = grpc.insecure_channel(f'{host}:{port}')
    return pb2_grpc.DataNodeServiceStub(channel)

# Generators
def chunk_generator(file_id, content):
    """Yields chunks needed for StoreChunk gRPC call"""
    offset = 0
    while offset < len(content):
        chunk = content[offset:offset+CHUNK_SIZE]
        yield pb2.FileChunk(
            file_id=file_id,
            content=chunk,
            offset=offset,
            is_last=(offset + len(chunk) >= len(content))
        )
        offset += len(chunk)

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
        
        meta = get_metadata_stub()
        
        # 1. Ask Metadata where to put it
        alloc = meta.AssignWrite(pb2.WriteRequest(
            filename=filename,
            size=size,
            tags=normalized_tags,
            owner_id=str(current_user.id),
            mime_type=file.content_type
        ))
        
        file_id = alloc.file_id
        target_nodes = alloc.target_nodes
        
        if not target_nodes:
            raise HTTPException(503, "No storage nodes available")
            
        # 2. Parallel Upload to DataNodes (Quorum W=2)
        success_count = 0
        
        # Simplified sequential upload for prototype (ideally async/parallel)
        for node in target_nodes:
            try:
                ds = get_datanode_stub(node.address, node.port)
                resp = ds.StoreChunk(chunk_generator(file_id, content))
                if resp.success:
                    success_count += 1
            except Exception as e:
                print(f"Failed to upload to {node.node_id}: {e}")
        
        if success_count < 2: # Quorum check
            # Rollback? (Not implemented yet, orphan data handling needed)
            raise HTTPException(500, f"Write Quorum failed. Success on {success_count}/3 nodes.")
            
        # 3. Commit Metadata
        meta.CommitWrite(pb2.CommitRequest(
            file_id=file_id,
            size=size,
            success=True
        ))
        
        return {
            "name": filename,
            "tags": normalized_tags,
            "size": size,
            "url": f"/files/{file_id}" # Use ID now, not filename
        }

    except Exception as e:
        print(e)
        raise HTTPException(500, str(e))

@app.get("/files/{file_id}")
async def download_file(file_id: str, current_user: User = Depends(get_current_active_user)):
    meta = get_metadata_stub()
    try:
        # 1. Locate File
        loc = meta.LocateFile(pb2.FileRequest(file_id=file_id))
        
        if not loc.replica_nodes:
            raise HTTPException(404, "File chunks not found")
            
        # 2. Read from random replica
        # Implements "Pull"
        import random
        node = random.choice(loc.replica_nodes)
        
        ds = get_datanode_stub(node.address, node.port)
        chunks_iter = ds.RetrieveChunk(pb2.FileRequest(file_id=file_id))
        
        def stream():
            for chunk in chunks_iter:
                yield chunk.content
                
        return StreamingResponse(
            stream(), 
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={loc.metadata.filename}"}
        )
        
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(404, "File not found")
        raise HTTPException(500, f"RPC Error: {e.details()}")

@app.get("/files")
async def list_files(tags: Optional[str] = None):
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    if tags:
        req.tags_filter.extend(tags.split(","))
        
    resp = meta.ListFiles(req)
    
    result = []
    for f in resp.files:
        result.append({
            "name": f.metadata.filename,
            "tags": list(f.metadata.tags),
            "size": f.metadata.size,
            "url": f"/files/{f.file_id}" # ID based URL
        })
    return result

# Legacy/Extra endpoints...
# We should map 'GET /tags', 'GET /stats'.
# For brevity, implementing minimal requirement.
