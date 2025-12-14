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
# Lamport clock for event ordering
from lamport import LamportClock
# Gossip protocol for metadata propagation
from gossip import GossipProtocol
# Merkle tree for anti-entropy
from merkle import MerkleTree, compare_trees

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
active_nodes_lock = threading.Lock()  # Lock for thread-safe access
files_metadata = {} # {file_id: {filename, size, tags, replicas: [], version_vector: {}, lamport_time: 0}}
metadata_service_instance = None  # Will be set after service creation
bully = None  # Will be initialized after service creation
lamport_clock = LamportClock()  # Global Lamport clock
gossip = None  # Will be initialized after service creation

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
    global bully
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MULTICAST_PORT))
    # Unicast support: generic UDP listener
    
    
    print(f"[Metadata] Listening for heartbeats on {MULTICAST_GROUP}:{MULTICAST_PORT}", flush=True)
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode('utf-8')
            
            # Handle both DataNode and Metadata heartbeats
            if msg.startswith('METADATA:'):
                # Format: METADATA:node_id:address:port
                parts = msg.split(':')
                if len(parts) >= 4:
                    node_id = int(parts[1])
                    node_ip = parts[2]
                    port = int(parts[3])
                    
                    # Register with Bully if this is a peer Metadata node
                    if node_id != NODE_ID and bully:
                        is_new = node_id not in bully.all_nodes
                        bully.register_node(node_id, f"{node_ip}:{port}")
                        if is_new:
                            print(f"[Metadata] Discovered peer Metadata node {node_id} at {node_ip}:{port}", flush=True)
            else:
                # DataNode heartbeat format: NODE_ID|IP|PORT|LOAD
                parts = msg.split('|')
                if len(parts) >= 3:
                    node_id = parts[0]
                    node_ip = parts[1]
                    port = int(parts[2])
                    
                    is_new = node_id not in active_nodes
                    ip_changed = not is_new and active_nodes[node_id]["address"] != node_ip
                    
                    with active_nodes_lock:
                        active_nodes[node_id] = {
                            "address": node_ip,
                            "port": port,
                            "last_seen": time.time()
                        }
                    
                    if is_new or ip_changed:
                        print(f"[Metadata] Registered DataNode {node_id} at {node_ip}:{port}", flush=True)
        except Exception as e:
            print(f"Listener error: {e}", flush=True)

def heartbeat_sender():
    """Sends Metadata node heartbeats to multicast group"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    
    # Get local IP
    local_ip = socket.gethostbyname(socket.gethostname())
    
    print(f"[Metadata] Starting heartbeat sender (NODE_ID={NODE_ID})", flush=True)
    
    while True:
        try:
            # Send Metadata heartbeat: METADATA:node_id:address:port
            msg = f"METADATA:{NODE_ID}:{local_ip}:{PORT}"
            sock.sendto(msg.encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
        except Exception as e:
            print(f"[Metadata] Heartbeat send error: {e}", flush=True)
        
        time.sleep(3)  # Send every 3 seconds

def node_monitor():
    """Checks for failed nodes and removes them"""
    while True:
        time.sleep(5)
        now = time.time()
        dead_nodes = []
        
        with active_nodes_lock:
            for node_id, info in list(active_nodes.items()):
                if now - info["last_seen"] > 10:
                    dead_nodes.append(node_id)
        
        for node_id in dead_nodes:
            print(f"[Metadata] DataNode {node_id} is dead, removing", flush=True)
            with active_nodes_lock:
                if node_id in active_nodes:
                    del active_nodes[node_id]

class MetadataService(pb2_grpc.MetadataServiceServicer):
    
    pending_uploads = {} # file_id -> {filename, tags, owner, nodes}

    def AssignWrite(self, request, context):
        # ... logic as above ...
        with active_nodes_lock:
            available = list(active_nodes.items())
        count = min(len(available), 3)
        selected = random.sample(available, count) if count > 0 else []
        
        print(f"[Metadata] AssignWrite: {len(available)} DataNodes available, selected {len(selected)}", flush=True)
        
        file_id = str(uuid.uuid4())
        
        # Cache intent
        self.pending_uploads[file_id] = {
            "filename": request.filename,
            "tags": request.tags,
            "owner": request.owner_id,
            "mime_type": request.mime_type,
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
        global bully, lamport_clock
        if bully and not bully.is_leader():
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            leader_id = bully.get_leader_id()
            context.set_details(f"Not leader. Current leader: {leader_id if leader_id else 'unknown'}")
            return pb2.CommitResponse(success=False, message="Not leader")
        
        if request.success and request.file_id in self.pending_uploads:
            # Increment Lamport clock for this write event
            lamport_time = lamport_clock.increment()
            
            data = self.pending_uploads.pop(request.file_id)
            
            # Initialize version vector for this file
            version_vector = {NODE_ID: 1}  # This node's first version of this file
            
            files_metadata[request.file_id] = {
                "filename": data["filename"],
                "tags": list(data["tags"]),
                "owner": data["owner"],
                "mime_type": data.get("mime_type", ""),
                "size": request.size,
                "replicas": data["replicas"],
                "created_at": int(time.time()),
                "lamport_time": lamport_time,
                "version_vector": version_vector
            }
            save_metadata()
            print(f"[Metadata] Committed file {data['filename']} ({request.file_id}) at Lamport time {lamport_time}")
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
        
        with active_nodes_lock:
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
        owner_filter = request.owner_filter if hasattr(request, 'owner_filter') else ""
        
        for fid, data in files_metadata.items():
            # Filter by owner if specified (non-admin users)
            if owner_filter and data.get("owner_id") != owner_filter:
                continue
            
            # AND logic for tags
            file_tags = set(data["tags"])
            if filter_tags and not filter_tags.issubset(file_tags):
                continue
                
            loc = pb2.FileLocation(file_id=fid)
            loc.metadata.filename = data["filename"]
            loc.metadata.size = data["size"]
            loc.metadata.tags.extend(data["tags"])
            loc.metadata.file_id = fid
            loc.metadata.owner_id = data.get("owner_id", "")
            loc.metadata.mime_type = data.get("mime_type", "")
            loc.metadata.created_at = data.get("created_at", 0)
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
    
    def GossipPush(self, request, context):
        """Handle incoming gossip push from peer"""
        global gossip
        if gossip:
            return gossip.handle_gossip_push(request)
        return pb2.GossipAck(ok=False, receiver_lamport_time=0)
    
    def GossipPull(self, request, context):
        """Handle gossip pull request (not implemented yet)"""
        # Can be implemented later for pull-based reconciliation
        return pb2.GossipUpdate(sender_id=NODE_ID, sender_lamport_time=lamport_clock.get_time())
    
    def CompareMerkleRoot(self, request, context):
        """
        Handle Merkle root comparison for anti-entropy.
        
        This RPC allows peers to efficiently detect metadata divergence
        after network partitions by comparing hash trees instead of
        sending all metadata.
        """
        global files_metadata
        
        # Build Merkle tree from current metadata
        my_tree = MerkleTree(files_metadata)
        my_root_hash = my_tree.get_root_hash()
        
        peer_root_hash = request.root_hash
        
        # Quick check: do roots match?
        if my_root_hash == peer_root_hash:
            print(f"[Merkle] Root hashes match with peer {request.sender_id} - no divergence", flush=True)
            return pb2.MerkleRootResponse(
                match=True,
                root_hash=my_root_hash,
                divergent_keys=[]
            )
        
        # Roots differ - need to identify which files diverge
        print(f"[Merkle] Root hash mismatch with peer {request.sender_id}, identifying divergent files...", flush=True)
        
        # Build tree from peer's leaf hashes for comparison
        peer_metadata = {}
        for leaf in request.leaf_hashes:
            # We don't have full peer data, but we can identify keys that differ
            peer_metadata[leaf.key] = {'hash': leaf.hash}
        
        # Identify files present in request but with different hashes or missing locally
        divergent_keys = []
        
        # Check files in peer's tree
        peer_keys = {leaf.key for leaf in request.leaf_hashes}
        my_keys = set(files_metadata.keys())
        
        # Files that differ or are missing
        for key in peer_keys:
            if key not in my_keys:
                divergent_keys.append(key)
            else:
                # Compare hashes
                my_file = files_metadata[key]
                my_hash = my_tree._hash_file(key, my_file)
                peer_hash = next((l.hash for l in request.leaf_hashes if l.key == key), None)
                if my_hash != peer_hash:
                    divergent_keys.append(key)
        
        # Files in my tree but not in peer's
        for key in my_keys - peer_keys:
            divergent_keys.append(key)
        
        print(f"[Merkle] Found {len(divergent_keys)} divergent file(s) with peer {request.sender_id}", flush=True)
        
        return pb2.MerkleRootResponse(
            match=False,
            root_hash=my_root_hash,
            divergent_keys=divergent_keys
        )


# Helper functions for Gossip protocolkle tree support
# Helper functions for Gossip protocol
def get_gossip_peers():
    """Return dict of peer Metadata nodes for gossip"""
    global bully
    if bully:
        return bully.all_nodes.copy()
    return {}

def get_gossip_metadata():
    """Return current files_metadata for gossip"""
    return files_metadata.copy()

def get_active_datanodes():
    """Return current active_nodes for gossip"""
    with active_nodes_lock:
        return active_nodes.copy()

def update_gossip_metadata(file_id, data):
    """Update files_metadata from gossip"""
    global files_metadata
    files_metadata[file_id] = data
    save_metadata()

def merge_active_datanodes(received_nodes):
    """Merge received DataNode registry from gossip"""
    with active_nodes_lock:
        for node_id, node_info in received_nodes.items():
            if node_id not in active_nodes:
                # New DataNode discovered via gossip
                active_nodes[node_id] = node_info
                print(f"[Gossip] Discovered DataNode {node_id} via gossip at {node_info['address']}:{node_info['port']}", flush=True)
            else:
                # Update if received info is more recent
                if node_info.get('last_seen', 0) > active_nodes[node_id].get('last_seen', 0):
                    active_nodes[node_id] = node_info


def anti_entropy_worker():
    """
    Periodic anti-entropy using Merkle trees.
    
    Runs every 60 seconds to compare metadata with peers
    using Merkle tree root hashes. If divergence detected,
    reconciles only the differing files.
    """
    global bully, files_metadata
    
    while True:
        time.sleep(60)  # Run every minute
        
        if not bully:
            continue
        
        peers = bully.all_nodes.copy()
        if not peers:
            continue
        
        # Build our Merkle tree
        my_tree = MerkleTree(files_metadata)
        my_root, my_leaves = my_tree.to_protobuf()
        
        print(f"[Anti-Entropy] Checking metadata consistency with {len(peers)} peer(s), root={my_root[:8]}...", flush=True)
        
        # Check each peer
        for peer_id, peer_addr in peers.items():
            if peer_id == NODE_ID:
                continue
            
            try:
                # Connect to peer
                channel = grpc.insecure_channel(peer_addr, options=[
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ])
                stub = pb2_grpc.MetadataServiceStub(channel)
                
                # Build comparison request
                request = pb2.MerkleRootRequest(
                    sender_id=NODE_ID,
                    root_hash=my_root
                )
                
                # Add leaf hashes for detailed comparison
                for file_id, leaf_hash in my_leaves:
                    request.leaf_hashes.append(pb2.MerkleLeaf(
                        key=file_id,
                        hash=leaf_hash
                    ))
                
                # Compare roots
                response = stub.CompareMerkleRoot(request, timeout=10)
                
                if response.match:
                    print(f"[Anti-Entropy] ✓ Consistent with peer {peer_id}", flush=True)
                else:
                    print(f"[Anti-Entropy] ✗ Divergence with peer {peer_id}: {len(response.divergent_keys)} file(s)", flush=True)
                    
                    # Reconciliation would happen here via Gossip or direct sync
                    # For now, Gossip will eventually propagate the differences
                    if response.divergent_keys:
                        print(f"[Anti-Entropy] Divergent files: {response.divergent_keys[:5]}...", flush=True)
                
                channel.close()
                
            except Exception as e:
                print(f"[Anti-Entropy] Failed to check peer {peer_id}: {e}", flush=True)


def serve():
    global bully, metadata_service_instance, gossip
    
    load_metadata()
    
    # Create service instance
    metadata_service_instance = MetadataService()
    
    # Initialize Bully algorithm
    bully = BullyLeaderElection(NODE_ID, metadata_service_instance)
    
    # Initialize Gossip protocol
    gossip = GossipProtocol(
        node_id=NODE_ID,
        get_peers_func=get_gossip_peers,
        get_metadata_func=get_gossip_metadata,
        update_metadata_func=update_gossip_metadata,
        lamport_clock=lamport_clock,
        get_datanodes_func=get_active_datanodes,
        merge_datanodes_func=merge_active_datanodes
    )
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_MetadataServiceServicer_to_server(metadata_service_instance, server)
    server.add_insecure_port(f'[::]:{PORT}')
    
    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=heartbeat_sender, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()
    threading.Thread(target=anti_entropy_worker, daemon=True).start()
    
    print(f"[Metadata] Service started on port {PORT} with NODE_ID={NODE_ID}", flush=True)
    server.start()
    
    # Start Bully election after server is running
    # Give time for other nodes to start
    time.sleep(5)
    print(f"[Metadata] Starting Bully leader election...", flush=True)
    bully.start()
    
    # Start Gossip protocol after peers discovered
    time.sleep(2)
    print(f"[Metadata] Starting Gossip protocol...", flush=True)
    gossip.start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()

