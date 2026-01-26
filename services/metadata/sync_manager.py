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
        self.node_id = node_id # Hostname del contenedor
        self.port = port
        self.service_name = "metadata" # Nombre del servicio en Docker Swarm

    def get_peer_ips(self):
        """Descubre las IPs de otros contenedores de metadata usando el DNS de Swarm"""
        try:
            # 'tasks.metadata' devuelve las IPs individuales de cada réplica en Swarm
            _, _, ips = socket.gethostbyname_ex(f"tasks.{self.service_name}")
            # Obtenemos nuestra propia IP
            my_ip = socket.gethostbyname(socket.gethostname())
            return [ip for ip in ips if ip != my_ip]
        except Exception as e:
            logger.error(f"Error descubriendo pares: {e}")
            return []

    def broadcast_update(self, file_id, meta_entry):
        """Envía la actualización a todos los vecinos descubiertos"""
        peers = self.get_peer_ips()
        if not peers:
            return

        # Construir el mensaje de Gossip basado en tu .proto
        # Usamos lamport_time como el campo de versión
        entry = pb2.FileMetadataEntry(
            file_id=file_id,
            filename=meta_entry['filename'],
            tags=meta_entry['tags'],
            owner=meta_entry['owner_id'],
            size=meta_entry['size'],
            replicas=meta_entry['replicas'],
            created_at=meta_entry['created_at'],
            lamport_time=meta_entry.get('lamport_time', 1)
        )
        
        update_msg = pb2.GossipUpdate(
            sender_id=int(hash(self.node_id) % 10**8), # ID numérico simple
            files=[entry]
        )

        for ip in peers:
            threading.Thread(target=self._send_push, args=(ip, update_msg), daemon=True).start()

    def _send_push(self, ip, message):
        """Intenta enviar el gRPC GossipPush a un vecino específico"""
        try:
            channel = grpc.insecure_channel(f"{ip}:{self.port}")
            stub = pb2_grpc.MetadataServiceStub(channel)
            stub.GossipPush(message, timeout=2)
            channel.close()
        except Exception as e:
            logger.debug(f"No se pudo sincronizar con {ip}: {e}")

    def request_pull_sync(self):
        """Elige un vecino al azar y le pide su base de datos completa"""
        peers = self.get_peer_ips()
        if not peers:
            return None
        
        target_ip = random.choice(peers)
        try:
            channel = grpc.insecure_channel(f"{target_ip}:{self.port}")
            stub = pb2_grpc.MetadataServiceStub(channel)
            # Según tu .proto: GossipPull(GossipRequest) returns (GossipUpdate)
            request = pb2.GossipRequest(requester_id=int(hash(self.node_id) % 10**8))
            response = stub.GossipPull(request, timeout=5)
            channel.close()
            return response
        except Exception as e:
            logger.warning(f"Fallo al realizar Gossip Pull contra {target_ip}: {e}")
            return None

    def periodic_sync_loop(self, metadata_service_instance):
        """Hilo que ejecuta el pull periódicamente (Anti-Entropy)"""
        import time
        logger.info("Iniciando bucle de Anti-Entropy (Periodic Pull)...")
        while True:
            # Sincronizar cada 30-60 segundos para evitar saturar la red
            time.sleep(random.randint(30, 60))
            response = self.request_pull_sync()
            if response:
                metadata_service_instance.process_gossip_update(response)        