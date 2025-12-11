"""
Bully Algorithm Implementation for Metadata Leader Election

Based on project requirements:
- Only the leader Metadata node can process write operations
- Dynamic leader election when current leader fails
- Ensures serialization of metadata modifications
"""
import time
import threading
import grpc
from enum import Enum
import os

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protos import service_pb2 as pb2
from protos import service_pb2_grpc as pb2_grpc


class NodeState(Enum):
    """Estado del nodo en el algoritmo de Bully"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class BullyLeaderElection:
    """
    Implementación del Algoritmo de Bully para elección de líder.
    
    El nodo con el ID más alto se convierte en líder.
    Cuando el líder falla, los nodos restantes inician una nueva elección.
    """
    
    def __init__(self, node_id, metadata_service):
        self.node_id = node_id
        self.metadata_service = metadata_service
        self.state = NodeState.FOLLOWER
        self.leader_id = None
        self.all_nodes = {}  # {node_id: address}
        
        # Timeouts
        self.election_timeout = 5  # segundos
        self.heartbeat_interval = 2  # segundos
        self.last_heartbeat_received = time.time()
        
        # Control de threads
        self.running = True
        self.election_in_progress = False
        
        print(f"[Bully] Node {self.node_id} initialized", flush=True)
    
    def register_node(self, node_id, address):
        """Registrar un nodo en el cluster"""
        self.all_nodes[node_id] = address
        print(f"[Bully] Registered node {node_id} at {address}", flush=True)
    
    def start(self):
        """Iniciar el proceso de elección de líder"""
        print(f"[Bully] Starting leader election process", flush=True)
        
        # Iniciar thread de monitoreo
        threading.Thread(target=self._monitor_leader, daemon=True).start()
        
        # Iniciar primera elección
        time.sleep(2)  # Esperar a que otros nodos se registren
        self.start_election()
    
    def start_election(self):
        """Iniciar proceso de elección"""
        if self.election_in_progress:
            return
        
        self.election_in_progress = True
        print(f"[Bully] Node {self.node_id} starting election", flush=True)
        self.state = NodeState.CANDIDATE
        
        # Enviar ELECTION a nodos con ID mayor
        higher_nodes = [nid for nid in self.all_nodes.keys() if nid > self.node_id]
        
        if not higher_nodes:
            # Soy el nodo con ID más alto, me proclamo líder
            self._become_leader()
            self.election_in_progress = False
            return
        
        # Enviar mensajes ELECTION
        responses = []
        for node_id in higher_nodes:
            try:
                address = self.all_nodes[node_id]
                channel = grpc.insecure_channel(address)
                stub = pb2_grpc.MetadataServiceStub(channel)
                
                response = stub.Election(
                    pb2.ElectionRequest(candidate_id=self.node_id),
                    timeout=2
                )
                
                if response.ok:
                    responses.append(node_id)
                    print(f"[Bully] Node {node_id} responded to election", flush=True)
                
                channel.close()
            except Exception as e:
                # Nodo no responde, probablemente caído
                print(f"[Bully] Node {node_id} did not respond: {e}", flush=True)
        
        if not responses:
            # Ningún nodo mayor respondió, soy el líder
            self._become_leader()
        else:
            # Esperar a que un nodo mayor se proclame líder
            print(f"[Bully] Waiting for higher node to become leader", flush=True)
            threading.Timer(self.election_timeout, self._check_leader_timeout).start()
        
        self.election_in_progress = False
    
    def _become_leader(self):
        """Proclamarse como líder"""
        print(f"[Bully] Node {self.node_id} is now LEADER", flush=True)
        self.state = NodeState.LEADER
        self.leader_id = self.node_id
        
        # Enviar COORDINATOR a todos los nodos
        for node_id in self.all_nodes.keys():
            if node_id != self.node_id:
                try:
                    address = self.all_nodes[node_id]
                    channel = grpc.insecure_channel(address)
                    stub = pb2_grpc.MetadataServiceStub(channel)
                    
                    stub.Coordinator(
                        pb2.CoordinatorRequest(leader_id=self.node_id),
                        timeout=2
                    )
                    
                    channel.close()
                    print(f"[Bully] Sent COORDINATOR to node {node_id}", flush=True)
                except Exception as e:
                    print(f"[Bully] Failed to send COORDINATOR to {node_id}: {e}", flush=True)
        
        # Iniciar envío de heartbeats
        self._send_heartbeats()
    
    def _send_heartbeats(self):
        """Enviar heartbeats como líder"""
        if not self.running or self.state != NodeState.LEADER:
            return
        
        for node_id in self.all_nodes.keys():
            if node_id != self.node_id:
                try:
                    address = self.all_nodes[node_id]
                    channel = grpc.insecure_channel(address)
                    stub = pb2_grpc.MetadataServiceStub(channel)
                    
                    stub.LeaderHeartbeat(
                        pb2.HeartbeatRequest(leader_id=self.node_id),
                        timeout=1
                    )
                    
                    channel.close()
                except:
                    pass  # Silenciar errores de heartbeat
        
        # Programar próximo heartbeat
        if self.running and self.state == NodeState.LEADER:
            threading.Timer(self.heartbeat_interval, self._send_heartbeats).start()
    
    def _monitor_leader(self):
        """Monitorear si el líder está activo"""
        while self.running:
            time.sleep(self.election_timeout)
            
            if self.state == NodeState.FOLLOWER:
                # Verificar si hemos recibido heartbeat del líder
                if time.time() - self.last_heartbeat_received > self.election_timeout:
                    print(f"[Bully] Leader timeout, starting election", flush=True)
                    self.start_election()
    
    def _check_leader_timeout(self):
        """Verificar si hay líder activo después de timeout"""
        if self.state == NodeState.CANDIDATE:
            # No se proclamó ningún líder, iniciar nueva elección
            print(f"[Bully] No leader elected, retrying", flush=True)
            self.start_election()
    
    def handle_election_request(self, candidate_id):
        """Manejar mensaje ELECTION de otro nodo"""
        print(f"[Bully] Received ELECTION from node {candidate_id}", flush=True)
        
        # Responder OK
        # Iniciar propia elección en background
        if candidate_id < self.node_id:
            threading.Thread(target=self.start_election, daemon=True).start()
        
        return True
    
    def handle_coordinator_message(self, leader_id):
        """Aceptar nuevo líder"""
        print(f"[Bully] Node {leader_id} is new leader", flush=True)
        self.state = NodeState.FOLLOWER
        self.leader_id = leader_id
        self.last_heartbeat_received = time.time()
        return True
    
    def handle_leader_heartbeat(self, leader_id):
        """Recibir heartbeat del líder"""
        self.last_heartbeat_received = time.time()
        
        if self.leader_id != leader_id:
            print(f"[Bully] Updating leader to {leader_id}", flush=True)
            self.leader_id = leader_id
            self.state = NodeState.FOLLOWER
        
        return True
    
    def is_leader(self):
        """Verificar si este nodo es el líder"""
        return self.state == NodeState.LEADER
    
    def get_leader_id(self):
        """Obtener ID del líder actual"""
        return self.leader_id
    
    def stop(self):
        """Detener el proceso de elección"""
        self.running = False
