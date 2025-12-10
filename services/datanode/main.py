import os
import time
import socket
import struct
import grpc
import threading
from concurrent import futures
from pathlib import Path

# Generated protos
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

# Configuration
NODE_ID = os.getenv("NODE_ID", f"datanode-{int(time.time())}")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "50051"))
MULTICAST_GROUP = os.getenv("MULTICAST_GROUP", "224.0.0.1")
MULTICAST_PORT = int(os.getenv("MULTICAST_PORT", "5000"))
STORAGE_DIR = Path("./data_node_storage")
CHUNK_SIZE = 1024 * 1024  # 1MB

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class DataNode(pb2_grpc.DataNodeServiceServicer):
    def Ping(self, request, context):
        return pb2.PingResponse(status="OK", node_id=NODE_ID)

    def StoreChunk(self, request_iterator, context):
        """Streaming write: Receives chunks and appends them to file"""
        file_id = None
        temp_path = None
        bytes_written = 0
        
        try:
            for chunk in request_iterator:
                if not file_id:
                    file_id = chunk.file_id
                    temp_path = STORAGE_DIR / f"{file_id}.tmp"
                
                with open(temp_path, "ab") as f:
                    f.write(chunk.content)
                    bytes_written += len(chunk.content)
            
            # Finalize file
            final_path = STORAGE_DIR / file_id
            if temp_path and temp_path.exists():
                temp_path.rename(final_path)
            
            print(f"[{NODE_ID}] Stored file {file_id} ({bytes_written} bytes)")
            return pb2.StoreResponse(success=True, message="Stored successfully", bytes_written=bytes_written)
            
        except Exception as e:
            print(f"Error storing file: {e}")
            if temp_path and temp_path.exists():
                os.remove(temp_path)
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

def heartbeat_sender():
    """Sends UDP multicast packets to announce presence"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    
    print(f"[{NODE_ID}] Specific ID sending heartbeats to {MULTICAST_GROUP}:{MULTICAST_PORT}")
    
    while True:
        try:
            # Message format: "NODE_ID|PORT|LOAD"
            # Simple text protocol for heartbeats
            msg = f"{NODE_ID}|{PORT}|0".encode('utf-8')
            sock.sendto(msg, (MULTICAST_GROUP, MULTICAST_PORT))
            time.sleep(5)
        except Exception as e:
            print(f"Heartbeat error: {e}")
            time.sleep(5)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_DataNodeServiceServicer_to_server(DataNode(), server)
    server.add_insecure_port(f'[::]:{PORT}')
    
    # Start Heartbeat thread
    hb_thread = threading.Thread(target=heartbeat_sender, daemon=True)
    hb_thread.start()
    
    print(f"[{NODE_ID}] DataNode started on port {PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
