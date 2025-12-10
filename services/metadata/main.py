import os
import time
import socket
import struct
import grpc
import threading
import json
import random
import uuid
from concurrent import futures
from pathlib import Path

# Generated protos
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

# Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "50051"))
MULTICAST_GROUP = os.getenv("MULTICAST_GROUP", "224.0.0.1")
MULTICAST_PORT = int(os.getenv("MULTICAST_PORT", "5000"))
DATA_DIR = Path("./metadata_storage")
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DB = DATA_DIR / "files.json"

# State
active_nodes = {} # {node_id: {address, port, last_seen}}
files_metadata = {} # {file_id: {filename, size, tags, replicas: []}}

# Persistence
def load_metadata():
    global files_metadata
    if FILES_DB.exists():
        try:
            with open(FILES_DB, "r") as f:
                files_metadata = json.load(f)
        except:
            files_metadata = {}

def save_metadata():
    with open(FILES_DB, "w") as f:
        json.dump(files_metadata, f)

# Background Tasks
def heartbeat_listener():
    """Listens for UDP heartbeats and updates registry"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MULTICAST_PORT))
    
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    print(f"[Metadata] Listening for heartbeats on {MULTICAST_GROUP}:{MULTICAST_PORT}")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode('utf-8')
            # Format: NODE_ID|PORT|LOAD
            parts = msg.split('|')
            if len(parts) >= 2:
                node_id = parts[0]
                port = int(parts[1])
                # Address is the sender's IP (addr[0])
                active_nodes[node_id] = {
                    "address": addr[0],
                    "port": port,
                    "last_seen": time.time()
                }
        except Exception as e:
            print(f"Listener error: {e}")

def node_monitor():
    """Removes dead nodes"""
    while True:
        now = time.time()
        dead = []
        for nid, info in active_nodes.items():
            if now - info["last_seen"] > 10: # 10s timeout
                dead.append(nid)
        
        for nid in dead:
            print(f"[Metadata] Node {nid} timed out")
            del active_nodes[nid]
        
        time.sleep(5)

class MetadataService(pb2_grpc.MetadataServiceServicer):
    def AssignWrite(self, request, context):
        """Standard N=3 replication strategy"""
        available = list(active_nodes.items())
        if len(available) < 1:
             # For dev/testing, allow 1, but warn
             # context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Not enough data nodes")
             pass
        
        # Select up to 3 random nodes
        count = min(len(available), 3)
        selected = random.sample(available, count)
        
        file_id = str(uuid.uuid4())
        
        response = pb2.WriteAllocation(file_id=file_id)
        for nid, info in selected:
            response.target_nodes.append(pb2.NodeInfo(
                node_id=nid,
                address=info["address"],
                port=info["port"]
            ))
            
        return response

    def CommitWrite(self, request, context):
        """Finalize metadata after successful upload"""
        if request.success:
            # In a real system we would know WHICH nodes succeeded. 
            # Simplified: Assume all assigned nodes succeeded if Gateway says success.
            # We need to store this partially? No, Gateway handled it.
            
            # We need to know the original write request details... 
            # In this simplified proto, we trust the gateway or should cache the 'pending' write.
            # For simplicity, we just log it as committed. 
            pass 
            
        return pb2.CommitResponse(success=True, message="Committed")

    # CUSTOM EXTENSION: We need a way to actually save the file metadata (name, tags)
    # The proto CommitWrite defined earlier was too simple.
    # Let's add a proper metadata save method or overload CommitWrite?
    # Actually, let's assume the Gateway calls AddFileMetadata (missing from my proto!)
    # I will modify this to use 'AddTags' or 'CommitWrite' properly. 
    # Let's use a workaround: The Gateway sends metadata in a separate call or we expand CommitWrite?
    # I'll stick to the proto I defined: CommitWrite has size/success. 
    # Wait, the AssignWrite had the metadata! I should have cached it.
    
    # IMPROVEMENT: Let's use a specific RPC for registering the file *after* success.
    # Or better, just trust the Gateway to send a "RegisterFile" command.
    # I will use `AddTags` to associate tags, but I need `CreateFile`.
    # Current proto limitation: `CommitWrite` doesn't have filename/tags.
    # `AssignWrite` had them. I will store them in `pending_uploads`.
    
    pending_uploads = {} # file_id -> {filename, tags, owner, nodes}

    def AssignWrite(self, request, context):
        # ... logic as above ...
        available = list(active_nodes.items())
        count = min(len(available), 3)
        selected = random.sample(available, count) if count > 0 else []
        
        file_id = str(uuid.uuid4())
        
        # Cache intent
        self.pending_uploads[file_id] = {
            "filename": request.filename,
            "tags": request.tags,
            "owner": request.owner_id,
            "replicas": [nid for nid, _ in selected]
        }
        
        response = pb2.WriteAllocation(file_id=file_id)
        for nid, info in selected:
            response.target_nodes.append(pb2.NodeInfo(
                node_id=nid,
                address=info["address"],
                port=info["port"]
            ))
        return response

    def CommitWrite(self, request, context):
        if request.success and request.file_id in self.pending_uploads:
            data = self.pending_uploads.pop(request.file_id)
            files_metadata[request.file_id] = {
                "filename": data["filename"],
                "tags": data["tags"],
                "owner": data["owner"],
                "size": request.size,
                "replicas": data["replicas"],
                "created_at": time.time()
            }
            save_metadata()
            print(f"[Metadata] Committed file {data['filename']} ({request.file_id})")
            return pb2.CommitResponse(success=True)
        return pb2.CommitResponse(success=False, message="Invalid ID or pending data not found")

    def LocateFile(self, request, context):
        # Look by file_ID (or filename? Proto says file_id, but Gateway might user filename. 
        # Let's support searching by ID. Ideally we need a filename->id map.
        # For this prototype, we scan.
        
        target = None
        fid = request.file_id
        
        # Try direct ID
        if fid in files_metadata:
            target = files_metadata[fid]
            target_id = fid
        else:
            # Try by filename (inefficient scan)
            for k, v in files_metadata.items():
                if v["filename"] == fid:
                    target = v
                    target_id = k
                    break
        
        if not target:
             context.abort(grpc.StatusCode.NOT_FOUND, "File not found")
             return pb2.FileLocation()

        resp = pb2.FileLocation(file_id=target_id)
        resp.metadata.filename = target["filename"]
        resp.metadata.size = target["size"]
        resp.metadata.tags.extend(target["tags"])
        
        for nid in target["replicas"]:
            if nid in active_nodes:
                info = active_nodes[nid]
                resp.replica_nodes.append(pb2.NodeInfo(
                    node_id=nid, 
                    address=info["address"], 
                    port=info["port"]
                ))
        
        return resp

    def ListFiles(self, request, context):
        resp = pb2.ListResponse()
        filter_tags = set(request.tags_filter)
        
        for fid, data in files_metadata.items():
            # AND logic for tags
            file_tags = set(data["tags"])
            if filter_tags and not filter_tags.issubset(file_tags):
                continue
                
            loc = pb2.FileLocation(file_id=fid)
            loc.metadata.filename = data["filename"]
            loc.metadata.size = data["size"]
            loc.metadata.tags.extend(data["tags"])
            loc.metadata.file_id = fid
            resp.files.append(loc)
            
        return resp

def serve():
    load_metadata()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_MetadataServiceServicer_to_server(MetadataService(), server)
    server.add_insecure_port(f'[::]:{PORT}')
    
    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()
    
    print(f"[Metadata] Service started on port {PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
