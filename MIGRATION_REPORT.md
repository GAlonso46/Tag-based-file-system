# 🚀 Distributed System Migration Report

This document summarizes the architectural changes made to transform the Tag-Based File System into a distributed solution using Docker Swarm.

## 🏗️ Architectural Changes

### 1. From Monolith to Microservices
We split the original `api/main.py` into three distinct services to segregate responsibilities as per the technical report:

-   **Gateway Service** (`services/gateway/`):
    -   **Old Role**: The only backend.
    -   **New Role**: A lightweight REST interface. It receives user requests but delegates storage and logic to other services via gRPC.
    -   **Key Change**: Does not save files to disk anymore. It streams them to DataNodes.

-   **Metadata Service** (`services/metadata/`):
    -   **New Component**: The "Brain".
    -   **Responsibilities**:
        -   Maintains a generic "Files Database" (Metadata).
        -   **Service Registry**: Listens for UDP Heartbeats to know which DataNodes are alive.
        -   **Load Balancing**: Assigns new files to 3 random active nodes.
        -   **Consistency**: Implements Quorum logic (requires success from 2/3 nodes).

-   **DataNode Service** (`services/datanode/`):
    -   **New Component**: The "Muscle".
    -   **Responsibilities**:
        -   Stores raw bytes (`.tmp` -> final file).
        -   **Heartbeats**: Broadcasts presence via UDP every 5 seconds.

### 2. Communication Protocols
-   **gRPC (Protocol Buffers)**: Replaced internal function calls.
    -   Defined in `protos/service.proto`.
    -   Used for extremely fast inter-service communication (Gateway -> Metadata, Gateway -> DataNodes).
-   **UDP Multicast**: Used for node discovery (Heartbeats).

## 📂 New File Structure

```
Tag-based-file-system/
├── protos/                 # Service Definitions (.proto)
├── services/
│   ├── gateway/            # FastAPI + gRPC Logic
│   ├── metadata/           # Registry + Coordination Logic
│   └── datanode/           # Storage + Heartbeat Logic
├── tests/
│   └── test_distributed_flow.py  # End-to-End Test Script
├── docker-stack-distributed.yml  # Swarm Deployment Config
├── Dockerfile.backend            # Generic image builder
├── build-images.sh               # Build script for Linux
└── README_DISTRIBUTED.md         # Deployment Guide
```

## 🧪 Verification & Testing Plan

To ensure the system works as expected on Ubuntu/Swarm, perform the following tests (detailed in `README_DISTRIBUTED.md`):

1.  **UDP Connectivity Check**: Verify `tagfs_metadata` logs show "Valid Heartbeat" from nodes.
2.  **Replication Check**: Upload a file and check if it physically exists in 3 different DataNode containers.
    -   `docker exec -it <datanode_id> ls /app/data_node_storage`
3.  **Fault Tolerance (The "Chaos" Test)**:
    -   Upload a file.
    -   Kill one DataNode: `docker service scale tagfs_datanode=2`.
    -   Try to download the file. It should still work (fetching from the remaining 2).
4.  **End-to-End Script**:
    -   Run `./test_distributed.sh` to validate the full API flow automatically.

## 📝 Next Steps for You
1.  Push this branch (`distributed-architecture`) to your git remote.
2.  Pull it on your Ubuntu machine.
3.  Follow `README_DISTRIBUTED.md`.
