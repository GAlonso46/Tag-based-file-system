import socket
import grpc
import logging
import random
from concurrent.futures import ThreadPoolExecutor
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

logger = logging.getLogger("SyncManager")

class SyncManager:
    def __init__(self, node_id, port=50051):
        self.node_id = node_id
        self.port = port
        # Thread pool para gossip asíncrono (no bloquea CommitWrite)
        self.gossip_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="gossip")

    # ==========================================================
    # DNS DISCOVERY VIA ALIAS
    # ==========================================================
    def get_peer_ips(self):
        """
        Resuelve dinámicamente todas las IPs asociadas al alias
        'metadata_service' y filtra su propia IP.
        """
        peers = set()
        try:
            results = socket.getaddrinfo(
                "metadata_service",
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM
            )

            for r in results:
                peers.add(r[4][0])

            my_ip = socket.gethostbyname(socket.gethostname())

            return [ip for ip in peers if ip != my_ip]

        except Exception as e:
            logger.error(f"Error resolviendo metadata_service: {e}")
            return []

    # ==========================================================
    # GOSSIP PUSH
    # ==========================================================
    def broadcast_update(self, file_id, meta_entry):
        """
        Broadcast asíncrono: encola y retorna inmediatamente.
        NO bloquea al caller (CommitWrite).
        """
        # Encolar en thread pool (retorna inmediatamente)
        self.gossip_executor.submit(self._do_broadcast, file_id, meta_entry)
        
    def broadcast_pending(self, pending_data):
        """
        Replica la intención de escritura (pending upload) a otros nodos.
        Esto permite que CommitWrite pueda llegar a CUALQUIER nodo.
        """
        self.gossip_executor.submit(self._do_broadcast_pending, pending_data)
    
    def _do_broadcast_pending(self, data):
        peers = self.get_peer_ips()
        if not peers:
            return
            
        entry = pb2.PendingUploadEntry(
            file_id=data["file_id"],
            filename=data["filename"],
            tags=data.get("tags", []),
            owner_id=data.get("owner_id", ""),
            mime_type=data.get("mime_type", ""),
            replicas_expected=data.get("replicas_expected", [])
        )
        
        for ip in peers:
            self.gossip_executor.submit(self._send_pending, ip, entry)

    def _send_pending(self, ip, message):
        try:
            channel = grpc.insecure_channel(f"{ip}:{self.port}")
            stub = pb2_grpc.MetadataServiceStub(channel)
            stub.PropagatePending(message, timeout=2)
            channel.close()
        except Exception:
            pass

    def _do_broadcast(self, file_id, meta_entry):
        """Worker que ejecuta el broadcast real en background."""
        peers = self.get_peer_ips()
        if not peers:
            return

        entry = pb2.FileMetadataEntry(
            file_id=file_id,
            filename=meta_entry.get("filename", ""),
            tags=meta_entry.get("tags", []),
            owner=meta_entry.get("owner_id", ""),
            size=meta_entry.get("size", 0),
            replicas=meta_entry.get("replicas", []),
            created_at=meta_entry.get("created_at", 0),
            lamport_time=meta_entry.get("lamport_time", 0),
            is_deleted=meta_entry.get("is_deleted", False)
        )

        update_msg = pb2.GossipUpdate(
            sender_id=int(hash(self.node_id) % 10**8),
            files=[entry]
        )

        for ip in peers:
            # Usar thread pool para paralelizar envíos
            self.gossip_executor.submit(self._send_push, ip, update_msg)

    def _send_push(self, ip, message):
        try:
            channel = grpc.insecure_channel(f"{ip}:{self.port}")
            stub = pb2_grpc.MetadataServiceStub(channel)
            stub.GossipPush(message, timeout=3)
            channel.close()
        except Exception:
            pass

    # ==========================================================
    # GOSSIP PULL
    # ==========================================================
    def request_pull_sync(self):
        peers = self.get_peer_ips()
        if not peers:
            return None

        target_ip = random.choice(peers)

        try:
            channel = grpc.insecure_channel(f"{target_ip}:{self.port}")
            stub = pb2_grpc.MetadataServiceStub(channel)

            request = pb2.GossipRequest(
                requester_id=int(hash(self.node_id) % 10**8)
            )

            response = stub.GossipPull(request, timeout=5)
            channel.close()
            return response

        except Exception as e:
            logger.debug(f"GossipPull falló contra {target_ip}: {e}")
            return None

    # ==========================================================
    # ANTI-ENTROPY LOOP
    # ==========================================================
    def periodic_sync_loop(self, metadata_service_instance):
        import time
        logger.info("Anti-Entropy (Periodic Pull) iniciado")

        while True:
            time.sleep(random.randint(30, 60))

            response = self.request_pull_sync()
            if response:
                metadata_service_instance.process_gossip_update(response)
