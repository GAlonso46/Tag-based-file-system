# 🌐 Distributed Tag-Based File System - Ubuntu Guide

This guide details how to deploy and test the distributed version of the Tag-Based File System on an Ubuntu environment using Docker Swarm.

## 📋 Prerequisites

-   **Ubuntu 20.04+** (Recommended)
-   **Docker Engine** (20.10+)
-   **Docker Swarm** initialized (`docker swarm init`)
-   **Python 3** (for testing script)

## 🚀 1. Setup Environment

Clone the repository or copy the files to your Ubuntu machine. Ensure scripts are executable:

```bash
chmod +x build-images.sh
chmod +x test_distributed.sh
```

## 🏗️ 2. Build Images

Since this is a distributed architecture, we need to build generic images that can run as Gateway, Metadata, or DataNode services.

Run the build script:
```bash
./build-images.sh
```
*This handles compiling the Protocol Buffers (gRPC) and building both backend and frontend images.*

## 🌐 3. Deploy to Swarm

Deploy the stack to your Swarm cluster:

```bash
docker stack deploy -c docker-stack-distributed.yml tagfs
```

> **Note**: If you are using multiple physical nodes, you must distribute the images to valid workers.
> - **Option A (Easiest)**: Run `docker build` on EVERY node.
> - **Option B (Production)**: Use a local registry (localhost:5000).

## 🔍 4. Verification

Check that all services are up and running:

```bash
docker service ls
```
*You should see 1 `tagfs_gateway`, 1 `tagfs_metadata`, 3 `tagfs_datanode`.*

Check the Metadata Service logs to see if DataNodes are registering:

```bash
docker service logs tagfs_metadata -f
```
*Look for: `[Metadata] Listening for heartbeats...` and `Valid Heartbeat from...`*

## 🧪 5. Run Integration Tests

We have provided an automated test script to verify the entire flow (Register -> Token -> Upload -> Replication -> Download).

Run the test helper:
```bash
./test_distributed.sh
```

**Expected Output:**
```
🚀 Starting Distributed System Tests...
[TEST] Registering user...
[TEST] Logging in...
[TEST] Uploading file...
[TEST] Upload success! File ID: ...
[TEST] Listing files...
[TEST] Found file in list: ...
[TEST] Downloading file...
[TEST] Download content matches original!

✅ ALL TESTS PASSED!
```

## 🛠️ Troubleshooting

-   **Frontend Connection**: Open `http://localhost` (or your server IP) in your browser.
    -   If it fails to connect to API, ensure Nginx is configured to proxy to `gateway:8000`.
-   **UDP/Heartbeats**: If Metadata doesn't see DataNodes, check firewall rules allowing UDP port 5000 on the Overlay network.
    -   `ufw allow 5000/udp` (on all nodes if needed, though Docker usually manages this).
-   **Permissions**: If `docker build` fails, ensure you are running as root or user in `docker` group.
