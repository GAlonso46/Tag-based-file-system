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

# Bully algorithm for leader election
from bully import BullyLeaderElection

# Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "50051"))
MULTICAST_GROUP = os.getenv("MULTICAST_GROUP", "224.0.0.1")
MULTICAST_PORT = int(os.getenv("MULTICAST_PORT", "5000"))
DATA_DIR = Path("./metadata_storage")
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DB = DATA_DIR / "files.json"

# Bully configuration
NODE_ID = int(os.getenv("NODE_ID", str(hash(socket.gethostname()) % 1000)))
print(f"[Metadata] Starting with NODE_ID={NODE_ID}", flush=True)

# State
active_nodes = {} # {node_id: {address, port, last_seen}}
files_metadata = {} # {file_id: {filename, size, tags, replicas: []}}
metadata_service_instance = None  # Will be set after service creation
bully = None  # Will be initialized after service creation

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
    # Unicast support: generic UDP listener
    
    
    print(f"[Metadata] Listening for heartbeats on {MULTICAST_GROUP}:{MULTICAST_PORT}", flush=True)
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode('utf-8')
            # Updated format: NODE_ID|IP|PORT|LOAD
            parts = msg.split('|')
            if len(parts) >= 3:
                node_id = parts[0]
                node_ip = parts[1]  # Use IP from message, not socket
                port = int(parts[2])
                
                # Only log if this is a new node or IP changed
                is_new = node_id not in active_nodes
                ip_changed = not is_new and active_nodes[node_id]["address"] != node_ip
                
                active_nodes[node_id] = {
                    "address": node_ip,  # Use the IP sent by the DataNode
                    "port": port,
                    "last_seen": time.time()
                }
                
                if is_new or ip_changed:
                    print(f"[Metadata] Registered node {node_id} at {node_ip}:{port}", flush=True)
        except Exception as e:
            print(f"Listener error: {e}", flush=True)

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
        # BULLY: Only leader can process writes
        global bully
        if bully and not bully.is_leader():
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            leader_id = bully.get_leader_id()
            context.set_details(f"Not leader. Current leader: {leader_id if leader_id else 'unknown'}")
            return pb2.CommitResponse(success=False, message="Not leader")
        
        if request.success and request.file_id in self.pending_uploads:
            data = self.pending_uploads.pop(request.file_id)
            files_metadata[request.file_id] = {
                "filename": data["filename"],
                "tags": list(data["tags"]),  # Convert protobuf repeated field to list
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
    
    # ==================== BULLY ALGORITHM RPCs ====================
    
    def Election(self, request, context):
        """Handle ELECTION message from another node"""
        global bully
        if bully:
            ok = bully.handle_election_request(request.candidate_id)
            return pb2.ElectionResponse(ok=ok)
        return pb2.ElectionResponse(ok=False)
    
    def Coordinator(self, request, context):
        """Handle COORDINATOR message (new leader announcement)"""
        global bully
        if bully:
            ok = bully.handle_coordinator_message(request.leader_id)
            return pb2.CoordinatorResponse(ok=ok)
        return pb2.CoordinatorResponse(ok=False)
    
    def LeaderHeartbeat(self, request, context):
        """Handle heartbeat from leader"""
        global bully
        if bully:
            ok = bully.handle_leader_heartbeat(request.leader_id)
            return pb2.HeartbeatResponse(ok=ok)
        return pb2.HeartbeatResponse(ok=False)


def serve():
    global bully, metadata_service_instance
    
    load_metadata()
    
    # Create service instance
    metadata_service_instance = MetadataService()
    
    # Initialize Bully algorithm
    bully = BullyLeaderElection(NODE_ID, metadata_service_instance)
    
    # TODO: Register other metadata nodes when they become known
    # For now, nodes will discover each other through heartbeats
    # In production, this could be configured via environment variables
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_MetadataServiceServicer_to_server(metadata_service_instance, server)
    server.add_insecure_port(f'[::]:{PORT}')
    
    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()
    
    print(f"[Metadata] Service started on port {PORT} with NODE_ID={NODE_ID}", flush=True)
    server.start()
    
    # Start Bully election after server is running
    # Give time for other nodes to start
    time.sleep(5)
    print(f"[Metadata] Starting Bully leader election...", flush=True)
    bully.start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()

