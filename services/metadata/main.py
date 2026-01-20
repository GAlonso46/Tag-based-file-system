import os
import time
import socket
import struct
import grpc
import threading
import json
import random
import uuid
import hashlib
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
# Use hostname to avoid collisions in shared volume
hostname = socket.gethostname()
FILES_DB = DATA_DIR / f"files_shared.json"
ENABLE_TLS = os.getenv("ENABLE_TLS", "false").lower() == "true"
CERT_DIR = os.getenv("CERT_DIR", "./certs")

# Bully configuration
# Persistence for NODE_ID to prevent identity loss on restart
NODE_ID_FILE = DATA_DIR / f"node_id_shared"
def load_or_create_node_id():
    if NODE_ID_FILE.exists():
        try:
            with open(NODE_ID_FILE, "r") as f:
                return int(f.read().strip())
        except:
            pass
    # Generate stable ID if not exists
    # Use hash of hostname but ensure it's positive
    new_id = int(hash(socket.gethostname()) % 1000)
    if new_id < 0: new_id *= -1
    
    # Save it
    try:
        with open(NODE_ID_FILE, "w") as f:
            f.write(str(new_id))
    except:
        pass
    return new_id

NODE_ID = int(os.getenv("NODE_ID", load_or_create_node_id()))
EXPECTED_METADATA_REPLICAS = int(os.getenv("EXPECTED_METADATA_REPLICAS", "3"))
print(f"[Metadata] Starting with persistent NODE_ID={NODE_ID}, expecting {EXPECTED_METADATA_REPLICAS} total replicas", flush=True)

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
    """Atomic write to prevent corruption on crash"""
    temp_file = FILES_DB.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(files_metadata, f)
        # Atomic replacement (POSIX)
        temp_file.replace(FILES_DB)
    except Exception as e:
        print(f"[Metadata] Failed to save metadata: {e}", flush=True)
        if temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

# Background Tasks
def discover_metadata_peers():
    """
    Discover other metadata nodes using Docker Swarm DNS (tasks.metadata).
    Returns list of (node_id, address) tuples.
    """
    peers = []
    try:
        # Docker Swarm resolves tasks.metadata to all IPs of metadata service replicas
        hostname = "tasks.metadata"
        port = PORT
        
        # Resolve all IPs
        addrs = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
        ips = list(set([addr[4][0] for addr in addrs]))
        
        print(f"[Metadata] DNS resolved {len(ips)} metadata instances: {ips}", flush=True)
        
        # Ping each one to get their NODE_ID
        for ip in ips:
            try:
                channel = grpc.insecure_channel(f"{ip}:{port}", options=[
                    ('grpc.max_receive_message_length', 100 * 1024 * 1024),
                ])
                stub = pb2_grpc.MetadataServiceStub(channel)
                
                response = stub.Ping(pb2.PingRequest(), timeout=5)
                peer_node_id = int(response.node_id)
                
                # Don't add ourselves
                if peer_node_id != NODE_ID:
                    peers.append((peer_node_id, f"{ip}:{port}"))
                    print(f"[Metadata] Discovered peer NODE_ID={peer_node_id} at {ip}:{port}", flush=True)
                
                channel.close()
            except Exception as e:
                print(f"[Metadata] Failed to ping {ip}:{port}: {e}", flush=True)
        
    except Exception as e:
        print(f"[Metadata] Error discovering peers: {e}", flush=True)
    
    return peers

def heartbeat_listener():
    """Listens for UDP heartbeats and updates registry"""
    global bully
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MULTICAST_PORT))
    # Unicast support: generic UDP listener
    
    
    print(f"[Metadata] Listening for heartbeats on {MULTICAST_GROUP}:{MULTICAST_PORT}", flush=True)
    
    # Also discover peers via DNS (Docker Swarm service discovery)
    threading.Thread(target=discover_metadata_peers_via_dns, daemon=True).start()
    
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

def discover_metadata_peers_via_dns():
    """Discover other metadata nodes using Docker Swarm DNS and gRPC registration"""
    global bully
    import socket as sock_module
    
    print("[Metadata] Starting peer discovery...", flush=True)
    start_time = time.time()
    discovered_peers = []
    unique_peers_found = set()
    
    # Try to discover peers for up to 15 seconds
    while time.time() - start_time < 15:
        try:
            # Docker Swarm DNS: tasks.<service_name> resolves to all task IPs
            service_name = "tasks.metadata"
            
            try:
                # Get all IPs for the service
                peer_ips = sock_module.gethostbyname_ex(service_name)[2]
                my_ip = sock_module.gethostbyname(sock_module.gethostname())
                
                for ip in peer_ips:
                    if ip != my_ip:  # Don't register ourselves
                        try:
                            # Connect to peer and get their actual NODE_ID via gRPC
                            channel = grpc.insecure_channel(f"{ip}:{PORT}", options=[
                                ('grpc.max_receive_message_length', 10 * 1024 * 1024),
                            ])
                            stub = pb2_grpc.MetadataServiceStub(channel)
                            
                            # Ping to check if reachable and get NODE_ID
                            response = stub.Ping(pb2.PingRequest(), timeout=1)
                            
                            if response and response.node_id:
                                peer_node_id = int(response.node_id)
                                unique_peers_found.add(peer_node_id)
                                
                                if bully and peer_node_id != NODE_ID:
                                    # Add to discovered list for return
                                    if (peer_node_id, f"{ip}:{PORT}") not in discovered_peers:
                                        discovered_peers.append((peer_node_id, f"{ip}:{PORT}"))
                                    
                                    # register_node() already handles locking internally
                                    if peer_node_id not in bully.all_nodes:
                                        bully.register_node(peer_node_id, f"{ip}:{PORT}")
                                        print(f"[Metadata] Discovered peer: node_id={peer_node_id} at {ip}:{PORT}", flush=True)
                            
                            channel.close()
                        except Exception:
                            # Peer not ready yet
                            pass
                
                # If we found all expected peers, we can return early
                if len(unique_peers_found) >= EXPECTED_METADATA_REPLICAS - 1:
                    print(f"[Metadata] Found all expected peers ({len(unique_peers_found)}), finishing discovery", flush=True)
                    break
                    
            except sock_module.gaierror:
                # DNS not yet available
                pass
                
        except Exception as e:
            print(f"[Metadata] Discovery error: {e}", flush=True)
        
        time.sleep(2)
        
    return discovered_peers

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
    """Checks for failed nodes and removes them, triggers re-replication"""
    print(f"[Metadata] Node monitor started - checking every 5s for T2=10s timeout", flush=True)
    while True:
        time.sleep(5)
        now =time.time()
        dead_nodes = []
        
        with active_nodes_lock:
            for node_id, info in list(active_nodes.items()):
                time_since_last_seen = now - info["last_seen"]
                if time_since_last_seen > 10:  # T2 = 10 seconds
                    dead_nodes.append(node_id)
                    print(f"[Metadata] DETECTED DEAD NODE: {node_id} (last seen {time_since_last_seen:.1f}s ago)", flush=True)
        
        for node_id in dead_nodes:
            print(f"[Metadata] ⚠️  DataNode {node_id} is DEAD, removing from registry", flush=True)
            with active_nodes_lock:
                if node_id in active_nodes:
                    del active_nodes[node_id]
            
            print(f"[Metadata] 🔄 Triggering re-replication for dead node {node_id}", flush=True)
            # Trigger re-replication for files that lost a replica
            trigger_re_replication(node_id)

def trigger_re_replication(dead_node_id):
    """
    Trigger re-replication for all files that had a replica on the dead node.
    Implements the Pull pattern: target node pulls data from source node.
    """
    print(f"[Re-replication] Scanning files affected by dead node {dead_node_id}", flush=True)
    
    affected_files = []
    
    # Find all files that had a replica on the dead node
    for file_id, metadata in files_metadata.items():
        if dead_node_id in metadata.get("replicas", []):
            affected_files.append((file_id, metadata))
    
    if not affected_files:
        print(f"[Re-replication] No files affected by node {dead_node_id}", flush=True)
        return
    
    print(f"[Re-replication] Found {len(affected_files)} files to re-replicate", flush=True)
    
    for file_id, metadata in affected_files:
        try:
            current_replicas = metadata["replicas"]
            
            # Remove dead node from replicas list
            current_replicas = [nid for nid in current_replicas if nid != dead_node_id]
            
            # Check if we need more replicas (target is N=3)
            target_replicas = 3
            if len(current_replicas) >= target_replicas:
                # Already have enough replicas
                files_metadata[file_id]["replicas"] = current_replicas
                save_metadata()
                continue
            
            # Find a source node (any healthy replica)
            with active_nodes_lock:
                source_candidates = [nid for nid in current_replicas if nid in active_nodes]
            
            if not source_candidates:
                print(f"[Re-replication] WARNING: No healthy replicas for file {file_id} ({metadata['filename']})", flush=True)
                continue
            
            source_node_id = random.choice(source_candidates)
            source_node_info = None
            with active_nodes_lock:
                source_node_info = active_nodes[source_node_id]
            
            # Find a target node (healthy node without this file)
            with active_nodes_lock:
                target_candidates = [
                    (nid, info) for nid, info in active_nodes.items() 
                    if nid not in current_replicas
                ]
            
            if not target_candidates:
                print(f"[Re-replication] No available DataNodes for re-replication of {file_id}", flush=True)
                continue
            
            target_node_id, target_node_info = random.choice(target_candidates)
            
            # Instruct target node to pull data from source node
            print(f"[Re-replication] Replicating {metadata['filename']} from {source_node_id} to {target_node_id}", flush=True)
            
            try:
                # Connect to target DataNode
                target_channel = grpc.insecure_channel(
                    f"{target_node_info['address']}:{target_node_info['port']}",
                    options=[
                        ('grpc.max_send_message_length', 50 * 1024 * 1024),
                        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                    ]
                )
                target_stub = pb2_grpc.DataNodeServiceStub(target_channel)
                
                # Create replication request (using existing messages)
                # We'll use StoreChunk by having target pull from source
                # First, get data from source
                source_channel = grpc.insecure_channel(
                    f"{source_node_info['address']}:{source_node_info['port']}",
                    options=[
                        ('grpc.max_send_message_length', 50 * 1024 * 1024),
                        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                    ]
                )
                source_stub = pb2_grpc.DataNodeServiceStub(source_channel)
                
                # Stream data from source to target
                chunks = source_stub.RetrieveChunk(pb2.FileRequest(file_id=file_id), timeout=60)
                response = target_stub.StoreChunk(chunks, timeout=60)
                
                if response.success:
                    # Update metadata: add target to replicas list
                    current_replicas.append(target_node_id)
                    files_metadata[file_id]["replicas"] = current_replicas
                    save_metadata()
                    print(f"[Re-replication] ✓ Successfully replicated {metadata['filename']} to {target_node_id}", flush=True)
                else:
                    print(f"[Re-replication] ✗ Failed to replicate {file_id}: {response.message}", flush=True)
                
                source_channel.close()
                target_channel.close()
                
            except Exception as e:
                print(f"[Re-replication] Error replicating {file_id}: {e}", flush=True)
        
        except Exception as e:
            print(f"[Re-replication] Error processing file {file_id}: {e}", flush=True)
    
    print(f"[Re-replication] Re-replication round complete for dead node {dead_node_id}", flush=True)

class MetadataService(pb2_grpc.MetadataServiceServicer):
    
    pending_uploads = {} # file_id -> {filename, tags, owner, nodes}

    def Ping(self, request, context):
        """Health check and NODE_ID exchange for peer discovery"""
        return pb2.PingResponse(
            status="ok",
            node_id=str(NODE_ID)
        )

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
            
            # Use actual successful nodes if provided involved in the transaction
            # This fixes the bug where failed nodes were recorded as replicas
            final_replicas = list(request.successful_nodes)
            if not final_replicas:
                # Fallback to intended replicas (e.g. old gateway)
                final_replicas = data["replicas"]
            
            files_metadata[request.file_id] = {
                "filename": data["filename"],
                "tags": list(data["tags"]),
                "owner": data["owner"],
                "mime_type": data.get("mime_type", ""),
                "size": request.size,
                "replicas": final_replicas,
                "created_at": int(time.time()),
                "lamport_time": lamport_time,
                "version_vector": version_vector
            }
            save_metadata()
            print(f"[Metadata] Committed file {data['filename']} ({request.file_id}) with replicas {final_replicas}")
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
            # Skip deleted files
            if data.get("deleted", False):
                continue
            
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
    
    def UpdateTags(self, request, context):
        """Update tags for a file (replaces existing tags)"""
        file_id = request.file_id
        new_tags = list(request.tags)
        
        if file_id not in files_metadata:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"File {file_id} not found")
            return pb2.TagResponse(success=False)
        
        # Update tags in memory
        files_metadata[file_id]["tags"] = new_tags
        
        # Persist to disk
        metadata_store.update_file(file_id, {"tags": new_tags})
        
        # Propagate via gossip
        if gossip_protocol:
            gossip_protocol.trigger_push()
        
        logger.info(f"Updated tags for file {file_id}: {new_tags}")
        return pb2.TagResponse(success=True, current_tags=new_tags)
    
    def DeleteFile(self, request, context):
        """Delete a file (tombstone approach)"""
        file_id = request.file_id
        
        if file_id not in files_metadata:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"File {file_id} not found")
            return pb2.DeleteResponse(success=False)
        
        # Mark as deleted (tombstone)
        files_metadata[file_id]["deleted"] = True
        files_metadata[file_id]["deleted_at"] = int(time.time())
        
        # Persist to disk
        metadata_store.update_file(file_id, {
            "deleted": True,
            "deleted_at": int(time.time())
        })
        
        # Propagate via gossip
        if gossip_protocol:
            gossip_protocol.trigger_push()
        
        logger.info(f"Marked file {file_id} as deleted")
        return pb2.DeleteResponse(success=True)
    
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
    
    # Configure TLS if enabled
    if ENABLE_TLS:
        try:
            with open(f"{CERT_DIR}/server-key.pem", "rb") as f:
                server_key = f.read()
            with open(f"{CERT_DIR}/server-cert.pem", "rb") as f:
                server_cert = f.read()
            with open(f"{CERT_DIR}/ca-cert.pem", "rb") as f:
                ca_cert = f.read()
            
            server_credentials = grpc.ssl_server_credentials(
                [(server_key, server_cert)],
                root_certificates=ca_cert,
                require_client_auth=True
            )
            server.add_secure_port(f'[::]:{PORT}', server_credentials)
            print(f"[Metadata] TLS enabled on port {PORT}", flush=True)
        except Exception as e:
            print(f"[Metadata] Warning: Could not load TLS certificates: {e}", flush=True)
            print(f"[Metadata] Falling back to insecure mode", flush=True)
            server.add_insecure_port(f'[::]:{PORT}')
    else:
        server.add_insecure_port(f'[::]:{PORT}')
    
    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=heartbeat_sender, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()
    threading.Thread(target=anti_entropy_worker, daemon=True).start()
    
    print(f"[Metadata] Service started on port {PORT} with NODE_ID={NODE_ID}", flush=True)
    server.start()
    
    # CRITICAL: Discover metadata peers using DNS before starting election
    print(f"[Metadata] Discovering metadata peers via DNS...", flush=True)
    time.sleep(5)  # Give time for all replicas to start their gRPC servers
    
    try:
        peers = discover_metadata_peers()
        print(f"[Metadata] DEBUG: discover_metadata_peers() returned {len(peers)} peers", flush=True)
        
        # Register discovered peers with Bully
        for i, (peer_id, peer_addr) in enumerate(peers):
            print(f"[Metadata] DEBUG: Registering peer {i+1}/{len(peers)}: {peer_id} at {peer_addr}", flush=True)
            bully.register_node(peer_id, peer_addr)
            print(f"[Metadata] DEBUG: Successfully registered peer {peer_id}", flush=True)
        
        print(f"[Metadata] Registered {len(peers)} peers with Bully", flush=True)
    except Exception as e:
        print(f"[Metadata] ERROR in peer discovery/registration: {e}", flush=True)
        import traceback
        traceback.print_exc()
    
    print(f"[Metadata] DEBUG: After peer registration block", flush=True)
    
    # Wait a bit more if we haven't discovered all expected peers
    if len(peers) < EXPECTED_METADATA_REPLICAS - 1:
        print(f"[Metadata] Only found {len(peers)} peers, waiting 10s more...", flush=True)
        time.sleep(10)
        
        # Try discovery again
        new_peers = discover_metadata_peers()
        for peer_id, peer_addr in new_peers:
            bully.register_node(peer_id, peer_addr)
        
        total_peers = len(bully.all_nodes)
        print(f"[Metadata] After retry: {total_peers} total peers registered", flush=True)
    
    print(f"[Metadata] Starting Bully leader election with peers: {list(bully.all_nodes.keys())}", flush=True)
    bully.start()
    
    # Start Gossip protocol after peers discovered
    time.sleep(2)
    print(f"[Metadata] Starting Gossip protocol...", flush=True)
    gossip.start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()

