"""
Gossip Protocol Implementation for Metadata Propagation

Implements epidemic-style metadata synchronization between Metadata nodes.
Key features:
- Random peer selection (≤3 neighbors per round)
- Push-pull hybrid: push on writes, periodic pull for reconciliation
- Minimizes network overhead while ensuring eventual consistency
"""

import time
import random
import threading
import grpc

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protos import service_pb2 as pb2
from protos import service_pb2_grpc as pb2_grpc


class GossipProtocol:
    """
    Epidemic-style metadata propagation between Metadata nodes.
    
    According to informe_sd.md:
    - Selects ≤3 random neighbors per gossip round
    - Propagates metadata updates with O(1) per node overhead
    - Ensures exponentially fast propagation
    """
    
    def __init__(self, node_id, get_peers_func, get_metadata_func, update_metadata_func, lamport_clock, 
                 get_datanodes_func=None, merge_datanodes_func=None):
        self.node_id = node_id
        self.get_peers = get_peers_func  # Function that returns {node_id: address}
        self.get_metadata = get_metadata_func  # Function that returns files_metadata dict
        self.update_metadata = update_metadata_func  # Function to merge received metadata
        self.lamport_clock = lamport_clock
        self.get_datanodes = get_datanodes_func  # Function that returns active_nodes dict
        self.merge_datanodes = merge_datanodes_func  # Function to merge DataNode registry
        
        self.gossip_interval = 5  # seconds
        self.max_peers_per_round = 3
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the gossip background thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._gossip_worker, daemon=True)
            self.thread.start()
            print(f"[Gossip] Started gossip protocol (interval={self.gossip_interval}s)", flush=True)
    
    def stop(self):
        """Stop the gossip thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _gossip_worker(self):
        """Background worker that periodically gossips with random peers"""
        while self.running:
            try:
                self._gossip_round()
            except Exception as e:
                print(f"[Gossip] Error in gossip round: {e}", flush=True)
            
            time.sleep(self.gossip_interval)
    
    def _gossip_round(self):
        """Execute one round of gossip: select random peers and push metadata"""
        peers = self.get_peers()
        
        if not peers:
            return  # No peers to gossip with
        
        # Select up to 3 random peers
        peer_ids = list(peers.keys())
        selected_count = min(len(peer_ids), self.max_peers_per_round)
        selected_peers = random.sample(peer_ids, selected_count)
        
        # Get current metadata and DataNode registry snapshot
        metadata = self.get_metadata()
        datanodes = self.get_datanodes() if self.get_datanodes else {}
        
        if not metadata and not datanodes:
            return  # Nothing to share
        
        # Increment Lamport clock for gossip event
        lamport_time = self.lamport_clock.increment()
        
        # Push to each selected peer
        for peer_id in selected_peers:
            if peer_id == self.node_id:
                continue  # Don't gossip with self
            
            peer_address = peers[peer_id]
            self._push_to_peer(peer_id, peer_address, metadata, datanodes, lamport_time)
    
    def _push_to_peer(self, peer_id, peer_address, metadata, datanodes, lamport_time):
        """Push metadata and DataNode registry to a specific peer"""
        try:
            # Create gRPC channel
            channel = grpc.insecure_channel(peer_address, options=[
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ])
            stub = pb2_grpc.MetadataServiceStub(channel)
            
            # Build GossipUpdate message with files
            update = pb2.GossipUpdate(
                sender_id=self.node_id,
                sender_lamport_time=lamport_time
            )
            
            for file_id, file_data in metadata.items():
                # Convert version_vector keys from string to int
                version_vector = file_data.get("version_vector", {})
                converted_vv = {}
                for node_id_str, version in version_vector.items():
                    try:
                        converted_vv[int(node_id_str)] = int(version)
                    except (ValueError, TypeError):
                        # Skip invalid entries
                        pass
                
                entry = pb2.FileMetadataEntry(
                    file_id=file_id,
                    filename=file_data.get("filename", ""),
                    tags=file_data.get("tags", []),
                    owner=file_data.get("owner", ""),
                    size=file_data.get("size", 0),
                    replicas=file_data.get("replicas", []),
                    created_at=int(file_data.get("created_at", 0)),
                    lamport_time=file_data.get("lamport_time", 0),
                    version_vector=converted_vv
                )
                update.files.append(entry)
            
            # Add DataNode registry
            for node_id, node_info in datanodes.items():
                try:
                    # Convert port to int if it's a string
                    port = node_info.get("port", 0)
                    if isinstance(port, str):
                        port = int(port)
                    
                    dn_entry = pb2.DataNodeEntry(
                        node_id=node_id,
                        address=node_info.get("address", ""),
                        port=port,
                        last_seen=int(node_info.get("last_seen", 0))
                    )
                    update.datanodes.append(dn_entry)
                except Exception as e:
                    print(f"[Gossip] Error creating DataNodeEntry for {node_id}: {e}, port type={type(port)}, port={port}", flush=True)
                    raise
            
            # Send gossip push
            response = stub.GossipPush(update, timeout=5)
            
            if response.ok:
                # Update our Lamport clock with received time
                self.lamport_clock.update(response.receiver_lamport_time)
            
            channel.close()
            
        except grpc.RpcError as e:
            # Peer might be down or unreachable - this is normal in gossip
            pass
        except Exception as e:
            import traceback
            print(f"[Gossip] Error pushing to peer {peer_id}: {e}", flush=True)
            print(f"[Gossip] Traceback: {traceback.format_exc()}", flush=True)
    
    def handle_gossip_push(self, request):
        """
        Handle incoming gossip push from a peer.
        Merges received metadata using version vectors and DataNode registry.
        """
        # Update Lamport clock
        self.lamport_clock.update(request.sender_lamport_time)
        
        # Merge received file metadata
        for entry in request.files:
            self._merge_file_metadata(entry)
        
        # Merge received DataNode registry
        if self.merge_datanodes and request.datanodes:
            received_nodes = {}
            for dn in request.datanodes:
                received_nodes[dn.node_id] = {
                    "address": dn.address,
                    "port": dn.port,
                    "last_seen": dn.last_seen
                }
            self.merge_datanodes(received_nodes)
        
        # Return acknowledgment with our Lamport time
        return pb2.GossipAck(
            ok=True,
            receiver_lamport_time=self.lamport_clock.get_time()
        )
    
    def _merge_file_metadata(self, entry):
        """
        Merge received file metadata using version vectors.
        
        Version vector comparison:
        - If received dominates local: accept update
        - If local dominates received: ignore
        - If concurrent (neither dominates): resolve with Lamport timestamps (LWW)
        """
        files_metadata = self.get_metadata()
        file_id = entry.file_id
        
        # Convert version_vector keys from int back to string
        version_vector = {str(k): v for k, v in entry.version_vector.items()}
        
        received_data = {
            "filename": entry.filename,
            "tags": list(entry.tags),
            "owner": entry.owner,
            "size": entry.size,
            "replicas": list(entry.replicas),
            "created_at": entry.created_at,
            "lamport_time": entry.lamport_time,
            "version_vector": version_vector
        }
        
        if file_id not in files_metadata:
            # New file, accept it
            self.update_metadata(file_id, received_data)
            print(f"[Gossip] Received new file {entry.filename} from gossip", flush=True)
        else:
            # File exists, compare version vectors
            local_data = files_metadata[file_id]
            local_vv = local_data.get("version_vector", {})
            received_vv = received_data["version_vector"]
            
            if self._vector_dominates(received_vv, local_vv):
                # Received version is newer, accept it
                self.update_metadata(file_id, received_data)
                print(f"[Gossip] Updated file {entry.filename} from gossip (received dominates)", flush=True)
            elif self._vector_dominates(local_vv, received_vv):
                # Local version is newer, ignore received
                pass
            else:
                # Concurrent versions - use Lamport timestamp to break tie (LWW)
                local_lamport = local_data.get("lamport_time", 0)
                received_lamport = received_data["lamport_time"]
                
                if received_lamport > local_lamport:
                    self.update_metadata(file_id, received_data)
                    print(f"[Gossip] Resolved conflict for {entry.filename} using Lamport (received wins)", flush=True)
                # else: local wins, ignore received
    
    def _vector_dominates(self, v1, v2):
        """
        Check if version vector v1 dominates v2.
        v1 dominates v2 if: v1[i] >= v2[i] for all i, and v1[j] > v2[j] for at least one j
        """
        all_greater_or_equal = True
        at_least_one_greater = False
        
        # Check all keys in both vectors
        all_keys = set(v1.keys()) | set(v2.keys())
        
        for key in all_keys:
            v1_val = v1.get(key, 0)
            v2_val = v2.get(key, 0)
            
            if v1_val < v2_val:
                all_greater_or_equal = False
                break
            if v1_val > v2_val:
                at_least_one_greater = True
        
        return all_greater_or_equal and at_least_one_greater
