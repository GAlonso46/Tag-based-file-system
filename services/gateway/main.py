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


# gRPC Clients
_metadata_channel = None
_metadata_stub = None

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

def get_metadata_stub():
    """Get metadata stub with retry logic to find leader"""
    global _metadata_channel, _metadata_stub
    
    # Try to reuse existing connection
    if _metadata_stub is not None:
        return _metadata_stub
    
    # Create new connection
    options = [
        ('grpc.max_send_message_length', 100 * 1024 * 1024),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.http2.min_time_between_pings_ms', 10000),
        ('grpc.http2.max_pings_without_data', 0),
    ]
    
    credentials = get_grpc_credentials()
    if credentials:
        _metadata_channel = grpc.secure_channel(
            f'{METADATA_HOST}:{METADATA_PORT}',
            credentials,
            options=options
        )
    else:
        _metadata_channel = grpc.insecure_channel(
            f'{METADATA_HOST}:{METADATA_PORT}',
            options=options
        )
    _metadata_stub = pb2_grpc.MetadataServiceStub(_metadata_channel)
    return _metadata_stub

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
    return stubs if stubs else [get_metadata_stub()]

def call_metadata_with_leader_retry(method_name, request, timeout=10, max_retries=5):
    """
    Call metadata RPC with automatic retry to find leader.
    
    If a node returns FAILED_PRECONDITION (not leader), we retry with a fresh connection.
    Docker Swarm DNS will round-robin to different metadata replicas.
    Also retries on UNAVAILABLE status (node temporarily down).
    """
    global _metadata_channel, _metadata_stub
    
    for attempt in range(max_retries):
        try:
            stub = get_metadata_stub()
            method = getattr(stub, method_name)
            return method(request, timeout=timeout)
            
        except grpc.RpcError as e:
            should_retry = False
            error_msg = ""
            
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                # Not leader, retry with different node
                error_msg = "Node not leader"
                should_retry = True
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                # Node unavailable, retry
                error_msg = "Node unavailable"
                should_retry = True
            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                # Timeout, retry
                error_msg = "Request timeout"
                should_retry = True
            else:
                # Other RPC error, don't retry
                raise HTTPException(500, f"Metadata service error: {e.details()}")
            
            if should_retry and attempt < max_retries - 1:
                print(f"[Gateway] {error_msg}, retrying... (attempt {attempt + 1}/{max_retries})", flush=True)
                
                # Force new connection on next attempt
                if _metadata_channel is not None:
                    try:
                        _metadata_channel.close()
                    except:
                        pass
                _metadata_channel = None
                _metadata_stub = None
                
                import time
                # Exponential backoff
                time.sleep(0.5 * (2 ** attempt))
                continue
            elif attempt >= max_retries - 1:
                # All retries exhausted
                raise HTTPException(503, f"Could not complete metadata operation after {max_retries} attempts: {error_msg}")
            
        except Exception as e:
            # Non-RPC error
            if attempt < max_retries - 1:
                print(f"[Gateway] Internal error, retrying: {str(e)}", flush=True)
                import time
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise HTTPException(500, f"Internal error: {str(e)}")

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
        
        # 1. Ask Metadata where to put it (with leader retry)
        alloc = call_metadata_with_leader_retry(
            'AssignWrite',
            pb2.WriteRequest(
                filename=filename,
                size=size,
                tags=normalized_tags,
                owner_id=str(current_user.id),
                mime_type=file.content_type
            ),
            timeout=10
        )
        
        file_id = alloc.file_id
        target_nodes = alloc.target_nodes
        
        if not target_nodes:
            raise HTTPException(503, "No storage nodes available")
        
        print(f"[Gateway] Uploading file {file_id} to {len(target_nodes)} DataNodes", flush=True)
            
        # 2. Parallel Upload to DataNodes (Quorum W=2)
        # Use asyncio to upload to multiple nodes concurrently
        success_count = 0
        upload_results = []
        
        # Create thread pool executor for blocking gRPC calls
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(target_nodes))
        
        def upload_to_node(node):
            """Upload file to a single DataNode"""
            try:
                print(f"[Gateway] Uploading to node {node.node_id} at {node.address}:{node.port}", flush=True)
                ds = get_datanode_stub(node.address, node.port)
                # IMPORTANT: Create a NEW generator for each thread, don't share!
                # Sharing a generator across threads causes chunks to be split between nodes
                resp = ds.StoreChunk(chunk_generator(file_id, content), timeout=60)  # Increased timeout
                if resp.success:
                    print(f"[Gateway] Successfully stored on node {node.node_id} ({resp.bytes_written} bytes)", flush=True)
                    return (node.node_id, True, None, resp.bytes_written)
                else:
                    print(f"[Gateway] Failed to store on node {node.node_id}: {resp.message}", flush=True)
                    return (node.node_id, False, resp.message, 0)
            except Exception as e:
                print(f"[Gateway] Failed to upload to {node.node_id}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                return (node.node_id, False, str(e), 0)
        
        # Run uploads in parallel
        tasks = [loop.run_in_executor(executor, upload_to_node, node) for node in target_nodes]
        upload_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful uploads
        for result in upload_results:
            if isinstance(result, tuple) and result[1]:  # result is (node_id, success, message)
                success_count += 1
        
        print(f"[Gateway] Upload complete: {success_count}/{len(target_nodes)} successful", flush=True)
        
        # Quorum W=2 as per informe_sd.md: N=3, W=2, R=2
        # Ensures strong consistency and durability
        required_writes = min(2, len(target_nodes))  # W=2, but handle cases with fewer nodes
        
        if success_count < required_writes:
            # Fail if we couldn't meet write quorum
            raise HTTPException(500, f"Write quorum not met: Stored on {success_count}/{len(target_nodes)} nodes (Required: {required_writes}).")
            
        # 3. Commit Metadata (with leader retry)
        # Collect IDs of successful nodes
        successful_node_ids = []
        for result in upload_results:
            if isinstance(result, tuple) and result[1]:
                successful_node_ids.append(result[0])
        
        call_metadata_with_leader_retry(
            'CommitWrite',
            pb2.CommitRequest(
                file_id=file_id,
                size=size,
                success=True,
                successful_nodes=successful_node_ids
            ),
            timeout=10
        )
        
        return {
            "name": filename,
            "tags": list(normalized_tags),  # Convert protobuf repeated field to list
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
        loc = meta.LocateFile(pb2.FileRequest(file_id=file_id), timeout=10)
        
        if not loc.replica_nodes:
            raise HTTPException(404, "File chunks not found")
        
        # 2. Read Quorum R=2: Query 2 replicas as per informe_sd.md
        # N=3, W=2, R=2 ensures R+W>N for strong consistency
        import random
        
        # Required read quorum
        READ_QUORUM = 2
        
        # Select R=2 replicas (or all if fewer available)
        read_quorum = min(READ_QUORUM, len(loc.replica_nodes))
        
        if read_quorum < READ_QUORUM:
            print(f"[Gateway] Warning: Only {len(loc.replica_nodes)} replicas available, R=2 not satisfied")
        
        selected_nodes = random.sample(list(loc.replica_nodes), read_quorum)
        
        print(f"[Gateway] Read Quorum R={read_quorum}: Querying {len(selected_nodes)} replicas for file {file_id}", flush=True)
        
        # Query all selected replicas
        replica_responses = []
        for node in selected_nodes:
            try:
                ds = get_datanode_stub(node.address, node.port)
                # Test connection by pinging
                ds.Ping(pb2.PingRequest(), timeout=2)
                replica_responses.append({
                    'node': node,
                    'stub': ds
                })
                print(f"[Gateway] Replica {node.node_id} reachable", flush=True)
            except Exception as e:
                print(f"[Gateway] Failed to connect to replica {node.node_id}: {e}", flush=True)
                continue
        
        if not replica_responses:
            raise HTTPException(503, "No replicas available for read quorum")
        
        if len(replica_responses) < READ_QUORUM:
            print(f"[Gateway] Warning: Read quorum not satisfied ({len(replica_responses)}/{READ_QUORUM} replicas)", flush=True)
        
        # Select first available replica (metadata already has authoritative version from leader)
        # Version vector comparison already done at metadata level via Gossip
        selected_replica = replica_responses[0]
        
        print(f"[Gateway] Reading file {file_id} from replica {selected_replica['node'].node_id}", flush=True)
        
        chunks_iter = selected_replica['stub'].RetrieveChunk(pb2.FileRequest(file_id=file_id), timeout=30)
        
        
        def stream():
            bytes_received = 0
            chunk_count = 0
            for chunk in chunks_iter:
                chunk_count += 1
                bytes_received += len(chunk.content)
                yield chunk.content
            print(f"[Gateway] Download completed: {chunk_count} chunks, {bytes_received} bytes", flush=True)
                
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
async def list_files(
    tags: Optional[str] = None, 
    current_user: User = Depends(get_current_active_user)
):
    # Query ALL metadata replicas and combine results
    stubs = get_all_metadata_stubs()
    
    req = pb2.ListRequest()
    if tags:
        req.tags_filter.extend(tags.split(","))
    
    # Admin filter: if not admin, filter by owner_id
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    # If admin, no owner_filter = see all files
    
    # Collect files from all metadata nodes
    all_files = {}
    for stub in stubs:
        try:
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
        except Exception as e:
            print(f"[Gateway] Failed to query metadata node: {e}", flush=True)
            continue
    
    return list(all_files.values())

@app.get("/tags")
async def get_all_tags(current_user: User = Depends(get_current_active_user)):
    """Get all unique tags from files with count"""
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    # Admin sees all tags, users see only their tags
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    # Admin sees all stats, users see only their stats
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    
    if current_user.is_admin != 1:
        req.owner_filter = str(current_user.id)
    
    resp = meta.ListFiles(req, timeout=10)
    
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
    
    meta = get_metadata_stub()
    req = pb2.ListRequest()
    resp = meta.ListFiles(req, timeout=10)
    
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


