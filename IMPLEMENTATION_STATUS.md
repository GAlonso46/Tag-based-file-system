# Distributed System Implementation Summary

## ✅ Implemented Features (According to informe_sd.md)

### 1. **Metadata Node Discovery** ✅
- **Location**: `services/metadata/main.py` (lines 54-103, 104-121)
- **Implementation**:
  - Metadata nodes send UDP multicast heartbeats: `METADATA:node_id:address:port`
  - Format distinguishes from DataNode heartbeats
  - Heartbeats sent every 3 seconds on multicast group 224.0.0.1:5000
  - Peers automatically registered with Bully algorithm
- **Status**: COMPLETE - Enables Bully leader election

### 2. **Lamport Logical Clocks** ✅
- **Location**: `services/metadata/lamport.py`, `services/metadata/main.py`
- **Implementation**:
  - LamportClock class with increment(), update(), get_time()
  - Clock incremented on write operations (CommitWrite)
  - Stored with each file metadata entry
  - Used for conflict resolution (Last-Writer-Wins)
- **Status**: COMPLETE - Provides total event ordering

### 3. **Version Vectors** ✅
- **Location**: `services/metadata/main.py` (CommitWrite), `services/metadata/gossip.py`
- **Implementation**:
  - Each file has version_vector: {node_id: version}
  - Initialized on file creation
  - Used in gossip for conflict detection
  - Dominance checking: v1 dominates v2 if v1[i] >= v2[i] for all i
- **Status**: COMPLETE - Enables concurrent update detection

### 4. **Gossip Protocol** ✅
- **Location**: `services/metadata/gossip.py`
- **Implementation**:
  - Epidemic-style metadata propagation
  - Selects ≤3 random peers per round (every 5 seconds)
  - Push-based: sends FileMetadataEntry with version vectors
  - Conflict resolution using version vector dominance + Lamport timestamps
  - O(1) overhead per node, exponential propagation
- **Protobuf**: Added GossipUpdate, GossipAck, FileMetadataEntry messages
- **Status**: COMPLETE - Ensures eventual consistency

### 5. **Write Quorum W=2** ✅
- **Location**: `services/gateway/main.py` (line 119)
- **Implementation**:
  - Changed from W=1 to W=2
  - Gateway requires successful writes to 2 of 3 DataNodes
  - Meets informe_sd.md requirement: N=3, W=2, R=2
  - Strong consistency guarantee: R+W > N (2+2 > 3)
- **Status**: COMPLETE - Ensures durability

### 6. **Leader-Only Writes** ✅
- **Location**: `services/metadata/main.py` (CommitWrite method)
- **Implementation**:
  - Validates bully.is_leader() before processing writes
  - Returns FAILED_PRECONDITION if not leader
  - Serializes all metadata modifications through elected leader
- **Status**: COMPLETE - Prevents race conditions

### 7. **Bully Algorithm Enhancement** ✅
- **Location**: `services/metadata/bully.py` (existing), `services/metadata/main.py` (integration)
- **Implementation**:
  - Peer discovery via UDP multicast heartbeats
  - Automatic registration in bully.all_nodes dictionary
  - Leader election triggered 5 seconds after startup
  - Heartbeat interval: 2 seconds, election timeout: 5 seconds
- **Status**: NOW FUNCTIONAL - Previously coded but non-functional

## 📋 Protobuf Updates

### New Messages Added to `protos/service.proto`:

```protobuf
// Gossip Protocol
message FileMetadataEntry {
  string file_id = 1;
  string filename = 2;
  repeated string tags = 3;
  string owner = 4;
  int64 size = 5;
  repeated string replicas = 6;
  int64 created_at = 7;
  int64 lamport_time = 8;
  map<int32, int32> version_vector = 9;
}

message GossipUpdate {
  int32 sender_id = 1;
  int64 sender_lamport_time = 2;
  repeated FileMetadataEntry files = 3;
}

message GossipAck {
  bool ok = 1;
  int64 receiver_lamport_time = 2;
}

// Merkle Tree (placeholder for future)
message MerkleRootRequest {
  int32 sender_id = 1;
  string root_hash = 2;
}

message MerkleRootResponse {
  bool match = 1;
  string root_hash = 2;
  repeated string divergent_hashes = 3;
}
```

### New RPCs in MetadataService:

```protobuf
rpc GossipPush (GossipUpdate) returns (GossipAck);
rpc GossipPull (GossipRequest) returns (GossipUpdate);
rpc CompareMerkleRoot (MerkleRootRequest) returns (MerkleRootResponse);
```

## 🔄 Data Flow

### Write Operation (with all new features):
1. Gateway receives file upload
2. Gateway requests allocation from Metadata **LEADER**
3. Leader validates is_leader(), increments Lamport clock
4. Leader allocates 3 DataNodes, creates pending entry
5. Gateway uploads to DataNodes (requires W=2 successes)
6. Gateway commits to Leader
7. Leader increments Lamport clock, creates version vector
8. Leader persists metadata with lamport_time and version_vector
9. **Gossip propagates update to follower Metadata nodes (async)**
10. Followers merge using version vector comparison

### Metadata Synchronization (Gossip):
1. Every 5 seconds, each Metadata node gossips
2. Selects ≤3 random peers from bully.all_nodes
3. Pushes all files_metadata with version vectors
4. Receiver compares version vectors:
   - If received dominates: accept update
   - If local dominates: ignore
   - If concurrent: use Lamport timestamp (LWW)
5. Updates Lamport clocks on both sides

## 📁 Files Created/Modified

### New Files:
- `services/metadata/lamport.py` - Lamport clock implementation
- `services/metadata/gossip.py` - Gossip protocol implementation

### Modified Files:
- `services/metadata/main.py` - Integrated all features
- `services/gateway/main.py` - Updated W=2 quorum
- `protos/service.proto` - Added Gossip and Merkle messages

### Docker:
- `tagfs-backend:latest` rebuilt with new code
- Protobuf regenerated with new messages

## ⚠️ Not Yet Implemented (from informe_sd.md)

### 1. **Merkle Trees for Anti-Entropy**
- **Required**: Compare root hashes after partition recovery
- **Status**: Protobuf messages added, RPC handlers are placeholders
- **Effort**: ~1 week
- **Priority**: MEDIUM - Gossip provides eventual consistency

### 2. **Read Quorum R=2**
- **Required**: Query 2 DataNodes and compare version vectors
- **Current**: Gateway reads from single DataNode
- **Effort**: ~2 days
- **Priority**: HIGH - Needed for strong consistency guarantee

## 🧪 Testing Recommendations

### Test 1: Leader Election
```bash
# Deploy stack
docker stack deploy -c docker-stack-distributed.yml tagfs

# Watch logs - should see election
docker service logs -f tagfs_metadata

# Kill leader container
docker ps | grep metadata
docker kill <leader_container_id>

# Verify new leader elected within 5 seconds
```

### Test 2: Gossip Propagation
```bash
# Upload file
curl -X POST http://localhost:8000/files ...

# Check metadata on all 3 replicas
docker exec <metadata-1> cat /app/metadata_storage/files.json
docker exec <metadata-2> cat /app/metadata_storage/files.json
docker exec <metadata-3> cat /app/metadata_storage/files.json

# Should see same file_id with version_vector after ~5 seconds
```

### Test 3: Write Quorum W=2
```bash
# Stop 2 DataNodes
docker service scale tagfs_datanode=1

# Try upload - should fail (can't meet W=2)
curl -X POST http://localhost:8000/files ...
# Expected: "Write quorum not met: Stored on 1/1 nodes (Required: 2)"

# Restore DataNodes
docker service scale tagfs_datanode=3
```

### Test 4: Leader-Only Writes
```bash
# Upload file - should succeed
curl -X POST http://localhost:8000/files ...

# Kill current leader
docker kill <leader_id>

# Immediately try upload (before election completes)
curl -X POST http://localhost:8000/files ...
# Expected: May fail with "Not leader" during election

# Wait 5 seconds, retry - should succeed with new leader
```

## 📊 Compliance with informe_sd.md

| Requirement | Status | Evidence |
|-------------|--------|----------|
| **Bully Algorithm** | ✅ COMPLETE | `bully.py` + peer discovery via heartbeats |
| **Lamport Clocks** | ✅ COMPLETE | `lamport.py` + stored in metadata |
| **Version Vectors** | ✅ COMPLETE | Stored per file, used in gossip |
| **Gossip Protocol** | ✅ COMPLETE | `gossip.py` with ≤3 peer selection |
| **Merkle Trees** | ⚠️ PARTIAL | Protobuf defined, implementation pending |
| **Quorum N=3, W=2, R=2** | ⚠️ W=2 done, R=2 pending | Gateway enforces W=2 |
| **UDP Multicast Heartbeats** | ✅ COMPLETE | DataNodes + Metadata nodes |
| **Leader Serialization** | ✅ COMPLETE | CommitWrite validates is_leader() |
| **Eventual Consistency** | ✅ COMPLETE | Gossip + version vectors |
| **Conflict Resolution (LWW)** | ✅ COMPLETE | Lamport timestamps break ties |

## 🎯 Next Steps

### Immediate (Week 1):
1. **Implement R=2 reads** - Gateway should query 2 DataNodes and compare versions
2. **Test distributed deployment** - Deploy on 2+ physical machines with Docker Swarm
3. **Test partition recovery** - Verify gossip reconciles after network split

### Short-term (Week 2-3):
4. **Implement Merkle trees** - Build tree from files_metadata hashes
5. **Add anti-entropy process** - Periodic Merkle root comparison
6. **Enhanced monitoring** - Log gossip statistics, convergence time

### Long-term (Week 4+):
7. **TLS for gRPC** - As required by informe_sd.md security section
8. **JWT authentication** - Currently basic auth, should use JWT
9. **Auto-healing** - Detect under-replicated files and trigger re-replication

## 🚀 Deployment

System is ready for testing:

```bash
./build-images.sh
docker stack deploy -c docker-stack-distributed.yml tagfs
```

Configuration:
- 3 Metadata replicas (Bully + Gossip)
- 3 DataNode replicas (N=3)
- 1 Gateway replica
- Quorum: W=2, R=1 (R=2 pending)
- Gossip interval: 5 seconds
- Heartbeat interval: 3 seconds (Metadata), 5 seconds (DataNode)
