import os
import time
import socket
import struct
import grpc
import threading
import uuid
from concurrent import futures
from pathlib import Path

# Generated protos
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

# ===================== STORAGE CONFIGURATION =====================

# Base directory shared by all DataNode containers (via Docker volume)
BASE_STORAGE_DIR = Path("./data_node_storage")
BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# ===================== NODE ID =====================

def load_or_create_node_id():
    # Use the ACTUAL container hostname which is unique per replica
    actual_hostname = socket.gethostname()
    # For Docker Swarm replicas, hostname IS already unique
    node_id = f"datanode-{actual_hostname}"

    return node_id

NODE_ID = load_or_create_node_id()

# ===================== PER-NODE STORAGE DIR =====================

# Each DataNode stores files in its own subdirectory
STORAGE_DIR = BASE_STORAGE_DIR / NODE_ID
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Persist NODE_ID inside its own directory
NODE_ID_FILE = STORAGE_DIR / "node_id"

try:
    with open(NODE_ID_FILE, "w") as f:
        f.write(NODE_ID)
except Exception as e:
    print(f"Warning: Could not save NODE_ID: {e}", flush=True)

print(f"[DataNode] Started with NODE_ID: {NODE_ID}", flush=True)
print(f"[DataNode] Storage directory: {STORAGE_DIR}", flush=True)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "50051"))
MULTICAST_GROUP = os.getenv("MULTICAST_GROUP", "224.0.0.1")
MULTICAST_PORT = int(os.getenv("MULTICAST_PORT", "5000"))
CHUNK_SIZE = 1024 * 1024  # 1MB
ENABLE_TLS = os.getenv("ENABLE_TLS", "false").lower() == "true"
CERT_DIR = os.getenv("CERT_DIR", "./certs")

class DataNode(pb2_grpc.DataNodeServiceServicer):
    def Ping(self, request, context):
        return pb2.PingResponse(status="OK", node_id=NODE_ID)

    def StoreChunk(self, request_iterator, context):
        """Streaming write: Receives chunks and appends them to file"""
        file_id = None
        temp_path = None
        final_path = None
        bytes_written = 0
        chunks_received = 0
        file_handle = None
        
        try:
            for chunk in request_iterator:
                chunks_received += 1
                if not file_id:
                    file_id = chunk.file_id
                    # Use unique temp file to avoid race conditions from retries/concurrent uploads
                    temp_filename = f"{file_id}_{uuid.uuid4()}.tmp"
                    temp_path = STORAGE_DIR / temp_filename
                    final_path = STORAGE_DIR / file_id
                    # Open file ONCE and keep handle open
                    file_handle = open(temp_path, "wb")
                    print(f"[{NODE_ID}] Starting to receive file {file_id} (temp: {temp_filename})", flush=True)
                
                # Write to already-open file handle
                file_handle.write(chunk.content)
                file_handle.flush()  # Explicit flush after each chunk
                bytes_written += len(chunk.content)
                
                if chunk.is_last:
                    print(f"[{NODE_ID}] Received last chunk (#{chunks_received})", flush=True)
            
            print(f"[{NODE_ID}] Received {chunks_received} chunks, {bytes_written} bytes total", flush=True)
            
            # Close file before rename
            if file_handle:
                file_handle.close()
                file_handle = None
            
            # Rename temp to final
            if temp_path and temp_path.exists():
                temp_path.rename(final_path)
            
            # CRITICAL: Verify file size matches
            actual_size = final_path.stat().st_size
            if actual_size != bytes_written:
                error_msg = f"SIZE MISMATCH: wrote {bytes_written} bytes but file is {actual_size} bytes"
                print(f"[{NODE_ID}] ERROR: {error_msg}", flush=True)
                final_path.unlink()  # Delete corrupt file
                return pb2.StoreResponse(success=False, message=error_msg, bytes_written=0)
            
            print(f"[{NODE_ID}] ✓ Stored file {file_id} ({bytes_written} bytes, verified)", flush=True)
            return pb2.StoreResponse(success=True, message="Stored successfully", bytes_written=bytes_written)
            
        except Exception as e:
            print(f"[{NODE_ID}] Error storing file: {e}", flush=True)
            import traceback
            traceback.print_exc()
            
            # Cleanup
            if file_handle:
                try:
                    file_handle.close()
                except:
                    pass
            if temp_path and temp_path.exists():
                try:
                    os.remove(temp_path)
                except:
                    pass
            return pb2.StoreResponse(success=False, message=str(e), bytes_written=0)

    def RetrieveChunk(self, request, context):
        """Streaming read: Reads file and yields chunks"""
        file_path = STORAGE_DIR / request.file_id
        if not file_path.exists():
            context.abort(grpc.StatusCode.NOT_FOUND, "File not found")
            return

        print(f"[{NODE_ID}] Serving file {request.file_id}")
        offset = 0
        with open(file_path, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                yield pb2.FileChunk(
                    file_id=request.file_id,
                    content=data,
                    offset=offset,
                    is_last=False # Ideally logic here to determine last
                )
                offset += len(data)

    def DeleteFile(self, request, context):
        file_path = STORAGE_DIR / request.file_id
        if file_path.exists():
            os.remove(file_path)
            print(f"[{NODE_ID}] Deleted file {request.file_id}")
            return pb2.DeleteResponse(success=True, message="Deleted")
        else:
            return pb2.DeleteResponse(success=False, message="Not found")

def get_container_ip():
    """Get the container's IP address in the overlay network"""
    try:
        # Try to resolve our own hostname to get the container IP
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        print(f"Error getting container IP: {e}")
        return "127.0.0.1"

def heartbeat_sender():
    """Sends UDP packets to announce presence to all metadata nodes"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    
    # Get our container IP
    container_ip = get_container_ip()
    print(f"[{NODE_ID}] Container IP: {container_ip}", flush=True)
    print(f"[{NODE_ID}] Sending heartbeats to metadata service (port {MULTICAST_PORT})", flush=True)
    
    while True:
        try:
            # Docker Swarm: Resolve tasks.metadata to get all metadata IPs
            try:
                metadata_ips = socket.gethostbyname_ex("tasks.metadata")[2]
            except socket.gaierror:
                # Fallback: try the service name directly
                try:
                    metadata_ips = [socket.gethostbyname("metadata")]
                except:
                    metadata_ips = []
            
            if metadata_ips:
                # Message format: "NODE_ID|IP|PORT|LOAD"
                msg = f"{NODE_ID}|{container_ip}|{PORT}|0".encode('utf-8')
                
                # Send to each metadata replica
                for metadata_ip in metadata_ips:
                    try:
                        sock.sendto(msg, (metadata_ip, MULTICAST_PORT))
                    except Exception as e:
                        pass  # Silently ignore individual send failures
                
                if len(metadata_ips) > 1:
                    # Only log first time we discover multiple metadata nodes
                    pass
            
            time.sleep(5)
        except Exception as e:
            print(f"[{NODE_ID}] Heartbeat error: {e}", flush=True)
            time.sleep(5)

def serve():
    # Configure gRPC with larger message limits (critical for large files)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
        ]
    )
    pb2_grpc.add_DataNodeServiceServicer_to_server(DataNode(), server)
    
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
            print(f"[{NODE_ID}] TLS enabled on port {PORT}", flush=True)
        except Exception as e:
            print(f"[{NODE_ID}] Warning: Could not load TLS certificates: {e}", flush=True)
            print(f"[{NODE_ID}] Falling back to insecure mode", flush=True)
            server.add_insecure_port(f'[::]:{PORT}')
    else:
        server.add_insecure_port(f'[::]:{PORT}')
    
    # Start Heartbeat thread
    hb_thread = threading.Thread(target=heartbeat_sender, daemon=True)
    hb_thread.start()
    
    print(f"[{NODE_ID}] DataNode started on port {PORT}")
    server.start()
    server.wait_for_termination()

def cleanup_temp_files():
    """Periodically remove stale temp files older than 1 hour"""
    while True:
        try:
            now = time.time()
            for p in STORAGE_DIR.glob("*.tmp"):
                if now - p.stat().st_mtime > 3600: # 1 hour
                    try:
                        p.unlink()
                        print(f"[{NODE_ID}] Cleaned up stale temp file {p.name}", flush=True)
                    except Exception as e:
                        print(f"[{NODE_ID}] Failed to clean {p.name}: {e}", flush=True)
        except Exception as e:
            print(f"[{NODE_ID}] Cleanup error: {e}", flush=True)
        time.sleep(300) # Check every 5 mins

if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_temp_files, daemon=True)
    cleanup_thread.start()
    
    serve()
