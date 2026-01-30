import socket
import grpc
import logging
import threading
import random
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

logger = logging.getLogger("SyncManager")

class SyncManager:
    def __init__(self, node_id, port=50051):
        self.node_id = node_id
        self.port = port

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
            lamport_time=meta_entry.get("lamport_time", 0)
        )

        update_msg = pb2.GossipUpdate(
            sender_id=int(hash(self.node_id) % 10**8),
            files=[entry]
        )

        for ip in peers:
            threading.Thread(
                target=self._send_push,
                args=(ip, update_msg),
                daemon=True
            ).start()

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
