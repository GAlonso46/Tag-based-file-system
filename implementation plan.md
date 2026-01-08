Plan de Implementación Revisado - Alineado con Informe SD
🎯 Objetivo
Implementar los componentes de sistemas distribuidos faltantes según el informe del proyecto, priorizando:

Toma de decisiones distribuidas (Bully, Lamport, Vector Clocks)
Tolerancia a fallos nivel 2 (N=3, W=2, R=2)
Consistencia eventual (Gossip, Merkle Trees)
Infraestructura multi-nodo (Docker Swarm)
📋 Estado Actual vs Requisitos del Informe
Requisito Informe	Estado	Prioridad
Arquitectura 3 capas (Gateway, Metadata, DataNode)	✅ Implementado	-
Docker Swarm multi-nodo	✅ Configurado	-
gRPC para comunicación	✅ Implementado	-
UDP para heartbeats	✅ Implementado	-
Autenticación JWT	✅ Implementado	-
Replicación N=3	✅ Implementado	-
Algoritmo de Bully (Líder Metadata)	❌ FALTA	🔴 CRÍTICO
Relojes de Lamport	❌ FALTA	🔴 CRÍTICO
Vectores de Versión	❌ FALTA	🔴 CRÍTICO
Quorum W=2 (actualmente W=1)	⚠️ PARCIAL	🔴 CRÍTICO
Protocolo Gossip	❌ FALTA	🟡 IMPORTANTE
Árboles de Merkle	❌ FALTA	🟡 IMPORTANTE
Metadata persistente	❌ FALTA	🟡 IMPORTANTE
TLS/Cifrado	❌ FALTA	🟢 DESEABLE
🚀 FASE 1: Fundamentos Distribuidos (Semanas 1-3) 🔴 CRÍTICO
Tarea 1.1: Algoritmo de Bully para Elección de Líder Metadata
Objetivo: Implementar elección dinámica de líder para serializar escrituras de metadata

Contexto del Informe:

"Se garantiza que solo un nodo, el Líder del Metadata Service, sea responsable de serializar y autorizar todas las operaciones de modificación de etiquetas. Se utiliza el Algoritmo de Bully para la elección dinámica del Líder."

Implementación:

# services/metadata/bully.py (NUEVO)
import time
import threading
import grpc
from enum import Enum
class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"
class BullyLeaderElection:
    def __init__(self, node_id, all_nodes, metadata_stub):
        self.node_id = node_id
        self.all_nodes = all_nodes  # {node_id: address}
        self.state = NodeState.FOLLOWER
        self.leader_id = None
        self.metadata_stub = metadata_stub
        self.election_timeout = 5  # segundos
        self.heartbeat_interval = 2
        self.last_heartbeat = time.time()
        
    def start_election(self):
        """Inicia proceso de elección"""
        print(f"[Bully] Node {self.node_id} starting election", flush=True)
        self.state = NodeState.CANDIDATE
        
        # Enviar ELECTION a nodos con ID mayor
        higher_nodes = [nid for nid in self.all_nodes if nid > self.node_id]
        
        if not higher_nodes:
            # Soy el nodo con ID más alto, me proclamo líder
            self.become_leader()
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
            except:
                pass  # Nodo no responde
        
        if not responses:
            # Ningún nodo mayor respondió, soy el líder
            self.become_leader()
        else:
            # Esperar a que un nodo mayor se proclame líder
            threading.Timer(self.election_timeout, self.check_leader).start()
    
    def become_leader(self):
        """Proclamarse como líder"""
        print(f"[Bully] Node {self.node_id} is now LEADER", flush=True)
        self.state = NodeState.LEADER
        self.leader_id = self.node_id
        
        # Enviar COORDINATOR a todos los nodos menores
        for node_id in self.all_nodes:
            if node_id < self.node_id:
                try:
                    address = self.all_nodes[node_id]
                    channel = grpc.insecure_channel(address)
                    stub = pb2_grpc.MetadataServiceStub(channel)
                    stub.Coordinator(
                        pb2.CoordinatorRequest(leader_id=self.node_id),
                        timeout=2
                    )
                except:
                    pass
        
        # Iniciar envío de heartbeats
        self.send_heartbeats()
    
    def send_heartbeats(self):
        """Enviar heartbeats como líder"""
        if self.state == NodeState.LEADER:
            for node_id in self.all_nodes:
                if node_id != self.node_id:
                    try:
                        address = self.all_nodes[node_id]
                        channel = grpc.insecure_channel(address)
                        stub = pb2_grpc.MetadataServiceStub(channel)
                        stub.LeaderHeartbeat(
                            pb2.HeartbeatRequest(leader_id=self.node_id),
                            timeout=1
                        )
                    except:
                        pass
            
            # Programar próximo heartbeat
            threading.Timer(self.heartbeat_interval, self.send_heartbeats).start()
    
    def check_leader(self):
        """Verificar si hay líder activo"""
        if time.time() - self.last_heartbeat > self.election_timeout:
            # No hay líder, iniciar elección
            self.start_election()
    
    def is_leader(self):
        """Verificar si este nodo es el líder"""
        return self.state == NodeState.LEADER
Modificar 
services/metadata/main.py
:

from metadata.bully import BullyLeaderElection
# Inicializar Bully
NODE_ID = int(os.getenv("NODE_ID", str(hash(socket.gethostname()) % 1000)))
bully = None  # Se inicializa cuando se conocen todos los nodos
class MetadataService(pb2_grpc.MetadataServiceServicer):
    def CommitWrite(self, request, context):
        # Solo el líder puede procesar escrituras
        if not bully or not bully.is_leader():
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            context.set_details(f"Not leader. Current leader: {bully.leader_id if bully else 'unknown'}")
            return pb2.CommitResponse(success=False)
        
        # Procesar escritura...
    
    def Election(self, request, context):
        """Responder a mensaje ELECTION"""
        print(f"[Bully] Received ELECTION from {request.candidate_id}", flush=True)
        # Responder OK e iniciar propia elección
        threading.Thread(target=bully.start_election).start()
        return pb2.ElectionResponse(ok=True)
    
    def Coordinator(self, request, context):
        """Aceptar nuevo líder"""
        print(f"[Bully] Node {request.leader_id} is new leader", flush=True)
        bully.state = NodeState.FOLLOWER
        bully.leader_id = request.leader_id
        bully.last_heartbeat = time.time()
        return pb2.CoordinatorResponse(ok=True)
    
    def LeaderHeartbeat(self, request, context):
        """Recibir heartbeat del líder"""
        bully.last_heartbeat = time.time()
        bully.leader_id = request.leader_id
        return pb2.HeartbeatResponse(ok=True)
Actualizar 
protos/service.proto
:

message ElectionRequest {
    int32 candidate_id = 1;
}
message ElectionResponse {
    bool ok = 1;
}
message CoordinatorRequest {
    int32 leader_id = 1;
}
message CoordinatorResponse {
    bool ok = 1;
}
message HeartbeatRequest {
    int32 leader_id = 1;
}
message HeartbeatResponse {
    bool ok = 1;
}
service MetadataService {
    rpc Election(ElectionRequest) returns (ElectionResponse);
    rpc Coordinator(CoordinatorRequest) returns (CoordinatorResponse);
    rpc LeaderHeartbeat(HeartbeatRequest) returns (HeartbeatResponse);
    // ... métodos existentes
}
Criterios de Aceptación:

✅ Elección de líder funciona con 3 réplicas de Metadata
✅ Líder procesa escrituras, followers las rechazan
✅ Nueva elección tras caída del líder (<10s)
✅ Test de split-brain resuelto correctamente
Tiempo: 4-5 días

Tarea 1.2: Relojes de Lamport
Objetivo: Ordenación total de eventos de modificación de metadata

Contexto del Informe:

"Cada evento de modificación de etiquetas se marca con una marca de tiempo de Lamport. Esto permite al Líder de Metadatos resolver desempates."

Implementación:

# services/metadata/lamport.py (NUEVO)
import threading
class LamportClock:
    def __init__(self):
        self.time = 0
        self.lock = threading.Lock()
    
    def increment(self):
        """Incrementar reloj antes de enviar mensaje"""
        with self.lock:
            self.time += 1
            return self.time
    
    def update(self, received_time):
        """Actualizar reloj al recibir mensaje"""
        with self.lock:
            self.time = max(self.time, received_time) + 1
            return self.time
    
    def get_time(self):
        """Obtener tiempo actual"""
        with self.lock:
            return self.time
Modificar 
services/metadata/main.py
:

from metadata.lamport import LamportClock
lamport_clock = LamportClock()
class MetadataService(pb2_grpc.MetadataServiceServicer):
    def CommitWrite(self, request, context):
        if not bully.is_leader():
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            return pb2.CommitResponse(success=False)
        
        # Incrementar reloj de Lamport
        timestamp = lamport_clock.increment()
        
        # Guardar con timestamp
        session = SessionLocal()
        file_meta = FileMetadata(
            file_id=request.file_id,
            filename=data["filename"],
            tags=list(data["tags"]),
            owner=data["owner"],
            size=request.size,
            replicas=data["replicas"],
            created_at=time.time(),
            lamport_timestamp=timestamp  # NUEVO
        )
        session.add(file_meta)
        session.commit()
        
        # Propagar a followers con timestamp
        self.propagate_to_followers(file_meta, timestamp)
        
        return pb2.CommitResponse(success=True, timestamp=timestamp)
    
    def propagate_to_followers(self, file_meta, timestamp):
        """Propagar actualización a followers"""
        for node_id in bully.all_nodes:
            if node_id != bully.node_id:
                try:
                    address = bully.all_nodes[node_id]
                    channel = grpc.insecure_channel(address)
                    stub = pb2_grpc.MetadataServiceStub(channel)
                    stub.ReplicateMetadata(pb2.MetadataUpdate(
                        file_id=file_meta.file_id,
                        filename=file_meta.filename,
                        tags=file_meta.tags,
                        lamport_timestamp=timestamp
                    ))
                except:
                    pass
Criterios de Aceptación:

✅ Eventos ordenados causalmente
✅ Timestamps monotónicamente crecientes
✅ Resolución de conflictos por timestamp
Tiempo: 2 días

Tarea 1.3: Vectores de Versión
Objetivo: Detección de concurrencia y conflictos

Contexto del Informe:

"Los Vectores de Versión permiten la detección de concurrencia. Si dos actualizaciones provienen de diferentes particiones y ninguno de los vectores domina al otro, el sistema identifica un conflicto."

Implementación:

# services/metadata/vector_clock.py (NUEVO)
class VectorClock:
    def __init__(self, node_id, num_nodes):
        self.node_id = node_id
        self.vector = [0] * num_nodes
    
    def increment(self):
        """Incrementar componente propio"""
        self.vector[self.node_id] += 1
        return self.vector.copy()
    
    def update(self, other_vector):
        """Merge con vector recibido"""
        for i in range(len(self.vector)):
            self.vector[i] = max(self.vector[i], other_vector[i])
        self.vector[self.node_id] += 1
        return self.vector.copy()
    
    def compare(self, other_vector):
        """Comparar vectores: returns 'before', 'after', 'concurrent'"""
        less = False
        greater = False
        
        for i in range(len(self.vector)):
            if self.vector[i] < other_vector[i]:
                less = True
            if self.vector[i] > other_vector[i]:
                greater = True
        
        if less and not greater:
            return 'before'  # self happened before other
        elif greater and not less:
            return 'after'  # self happened after other
        elif not less and not greater:
            return 'equal'
        else:
            return 'concurrent'  # CONFLICTO
Uso en Metadata:

vector_clock = VectorClock(NODE_ID, num_metadata_nodes=3)
def detect_conflict(file_id, new_vector):
    """Detectar si hay conflicto de versiones"""
    session = SessionLocal()
    file_meta = session.query(FileMetadata).filter_by(file_id=file_id).first()
    
    if file_meta:
        current_vector = file_meta.vector_clock
        relation = vector_clock.compare(new_vector)
        
        if relation == 'concurrent':
            # CONFLICTO DETECTADO
            logger.warning(f"Conflict detected for file {file_id}")
            return True, current_vector, new_vector
    
    return False, None, None
Criterios de Aceptación:

✅ Detección de escrituras concurrentes
✅ Identificación de conflictos en particiones
✅ Resolución LWW (Last Writer Wins)
Tiempo: 3 días

Tarea 1.4: Ajustar Quorum a W=2
Objetivo: Cumplir con requisito del informe N=3, W=2, R=2

Contexto del Informe:

"Se establecen los siguientes parámetros: N=3, W=2, R=2. La condición R + W > N se cumple, asegurando consistencia fuerte."

Implementación:

# services/gateway/main.py
WRITE_QUORUM = int(os.getenv("WRITE_QUORUM", "2"))  # Cambiar de 1 a 2
READ_QUORUM = int(os.getenv("READ_QUORUM", "2"))
@app.post("/files")
def upload_file(...):
    # ...
    required_writes = min(WRITE_QUORUM, len(target_nodes))
    
    # Esperar a que W=2 nodos confirmen
    successful_writes = 0
    for future in as_completed(futures):
        if future.result():
            successful_writes += 1
            if successful_writes >= required_writes:
                break  # Quorum alcanzado
    
    if successful_writes < required_writes:
        # Abortar escritura, no se alcanzó quorum
        rollback_writes(file_id, successful_nodes)
        raise HTTPException(503, f"Write quorum not met: {successful_writes}/{required_writes}")
Criterios de Aceptación:

✅ W=2 requerido para escrituras exitosas
✅ R=2 para lecturas
✅ R + W > N garantizado (2 + 2 > 3)
✅ Tests pasan con nuevo quorum
Tiempo: 1-2 días

🔄 FASE 2: Consistencia Eventual (Semanas 4-5) 🟡 IMPORTANTE
Tarea 2.1: Protocolo Gossip
Objetivo: Propagación eficiente de metadatos entre nodos Metadata

Contexto del Informe:

"Las actualizaciones de etiquetas se propagan utilizando un protocolo Epidémico (Gossip). El Gossip selecciona periódicamente un subconjunto aleatorio de vecinos (≤3) para intercambiar información."

Implementación:

# services/metadata/gossip.py (NUEVO)
import random
import threading
import time
class GossipProtocol:
    def __init__(self, node_id, all_nodes, metadata_stub):
        self.node_id = node_id
        self.all_nodes = all_nodes
        self.metadata_stub = metadata_stub
        self.gossip_interval = 5  # segundos
        self.fanout = 3  # número de vecinos a contactar
        self.updates_buffer = []  # Buffer de actualizaciones pendientes
        
    def start(self):
        """Iniciar proceso de gossip"""
        threading.Thread(target=self.gossip_loop, daemon=True).start()
    
    def gossip_loop(self):
        """Loop principal de gossip"""
        while True:
            time.sleep(self.gossip_interval)
            self.gossip_round()
    
    def gossip_round(self):
        """Una ronda de gossip"""
        if not self.updates_buffer:
            return
        
        # Seleccionar vecinos aleatorios
        neighbors = random.sample(
            [n for n in self.all_nodes if n != self.node_id],
            min(self.fanout, len(self.all_nodes) - 1)
        )
        
        # Enviar actualizaciones a vecinos
        for neighbor_id in neighbors:
            try:
                address = self.all_nodes[neighbor_id]
                channel = grpc.insecure_channel(address)
                stub = pb2_grpc.MetadataServiceStub(channel)
                
                stub.GossipUpdates(pb2.GossipRequest(
                    sender_id=self.node_id,
                    updates=self.updates_buffer
                ))
            except:
                pass
    
    def add_update(self, update):
        """Añadir actualización al buffer"""
        self.updates_buffer.append(update)
        
        # Limitar tamaño del buffer
        if len(self.updates_buffer) > 100:
            self.updates_buffer = self.updates_buffer[-100:]
Criterios de Aceptación:

✅ Propagación exponencial de actualizaciones
✅ Convergencia en <30 segundos
✅ Tolerante a fallos de nodos
Tiempo: 3 días

Tarea 2.2: Árboles de Merkle para Anti-Entropy
Objetivo: Reconciliación eficiente tras particiones

Contexto del Informe:

"Para la reconciliación tras particiones, el sistema utiliza Árboles de Merkle. Cuando los nodos divergentes se reconectan, comparan los Hash Raíz. Si difieren, solo se intercambian las ramas que han cambiado."

Implementación:

# services/metadata/merkle.py (NUEVO)
import hashlib
import json
class MerkleTree:
    def __init__(self, data_dict):
        """
        data_dict: {file_id: metadata}
        """
        self.data = data_dict
        self.tree = self.build_tree()
    
    def build_tree(self):
        """Construir árbol de Merkle"""
        # Ordenar por file_id para consistencia
        sorted_items = sorted(self.data.items())
        
        # Crear hojas (hash de cada archivo)
        leaves = [self.hash_item(item) for item in sorted_items]
        
        # Construir árbol bottom-up
        tree = [leaves]
        while len(tree[-1]) > 1:
            level = []
            current = tree[-1]
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    combined = current[i] + current[i+1]
                else:
                    combined = current[i]
                level.append(hashlib.sha256(combined.encode()).hexdigest())
            tree.append(level)
        
        return tree
    
    def get_root_hash(self):
        """Obtener hash raíz"""
        return self.tree[-1][0] if self.tree[-1] else ""
    
    def hash_item(self, item):
        """Hash de un item (file_id, metadata)"""
        file_id, metadata = item
        data_str = json.dumps({
            'file_id': file_id,
            'tags': sorted(metadata.get('tags', [])),
            'owner': metadata.get('owner'),
            'lamport': metadata.get('lamport_timestamp', 0)
        }, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def find_differences(self, other_tree):
        """Encontrar diferencias con otro árbol"""
        if self.get_root_hash() == other_tree.get_root_hash():
            return []  # Árboles idénticos
        
        # Comparar nivel por nivel para encontrar diferencias
        differences = []
        # ... lógica de comparación
        return differences
Uso en Anti-Entropy:

def anti_entropy_sync(peer_node_id):
    """Sincronizar con peer usando Merkle trees"""
    # Construir árbol local
    local_tree = MerkleTree(get_all_metadata())
    
    # Obtener árbol remoto
    peer_tree = get_peer_merkle_tree(peer_node_id)
    
    # Comparar raíces
    if local_tree.get_root_hash() != peer_tree.get_root_hash():
        # Encontrar diferencias
        diffs = local_tree.find_differences(peer_tree)
        
        # Intercambiar solo datos diferentes
        for file_id in diffs:
            sync_file_metadata(peer_node_id, file_id)
Criterios de Aceptación:

✅ Detección eficiente de diferencias
✅ Sincronización solo de datos divergentes
✅ Reconciliación tras partición <60s
Tiempo: 4 días

💾 FASE 3: Persistencia y HA (Semanas 6-7) 🟡 IMPORTANTE
Tarea 3.1: Persistencia de Metadata (SQLite)
Implementar según plan original
Tiempo: 3-4 días
Tarea 3.2: Health Checks
Implementar según plan original
Tiempo: 2 días
Tarea 3.3: Metadata Service Multi-Replica
Desplegar 3 réplicas de Metadata
Configurar Bully entre réplicas
Tiempo: 2 días
🔐 FASE 4: Seguridad (Semana 8) 🟢 DESEABLE
Tarea 4.1: TLS para gRPC
Contexto del Informe:

"Todas las conexiones basadas en TCP/gRPC deben utilizar TLS."

Implementación:

# Generar certificados
$ openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
# services/gateway/main.py
import grpc
# Cargar certificados
with open('cert.pem', 'rb') as f:
    cert = f.read()
with open('key.pem', 'rb') as f:
    key = f.read()
# Crear canal seguro
credentials = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('metadata:50051', credentials)
Tiempo: 2 días

📊 Cronograma Revisado
Semana 1-3: FASE 1 - Fundamentos Distribuidos (CRÍTICO)
├─ Día 1-5:   Algoritmo de Bully
├─ Día 6-7:   Relojes de Lamport
├─ Día 8-10:  Vectores de Versión
└─ Día 11-12: Quorum W=2
Semana 4-5: FASE 2 - Consistencia Eventual
├─ Día 1-3:   Protocolo Gossip
└─ Día 4-7:   Árboles de Merkle
Semana 6-7: FASE 3 - Persistencia y HA
├─ Día 1-4:   Persistencia Metadata
├─ Día 5-6:   Health Checks
└─ Día 7-8:   Metadata Multi-Replica
Semana 8: FASE 4 - Seguridad
└─ Día 1-2:   TLS/gRPC
✅ Criterios de Éxito Alineados con Informe
Requisitos Obligatorios
✅ Infraestructura multi-nodo (mínimo 2 ordenadores)
✅ Toma de decisiones distribuidas (Bully + Lamport + Vector Clocks)
✅ Tolerancia a fallos nivel 2 (N=3, W=2, R=2, tolera 1 fallo)
Componentes Técnicos
✅ Algoritmo de Bully funcional
✅ Relojes de Lamport para ordenación
✅ Vectores de Versión para conflictos
✅ Quorum N=3, W=2, R=2
✅ Protocolo Gossip para propagación
✅ Árboles de Merkle para anti-entropy
✅ Metadata persistente
✅ TLS en comunicaciones
🎯 Priorización
CRÍTICO (Semanas 1-3):

Bully (requisito de toma de decisiones distribuidas)
Lamport (requisito de ordenación)
Vector Clocks (requisito de detección de conflictos)
Quorum W=2 (requisito de tolerancia nivel 2)
IMPORTANTE (Semanas 4-7): 5. Gossip (consistencia eventual) 6. Merkle Trees (reconciliación) 7. Persistencia (durabilidad)

DESEABLE (Semana 8): 8. TLS (seguridad)

📝 Notas de Implementación
Todas las implementaciones deben seguir el informe SD
Tests deben verificar cada componente distribuido
Documentación debe referenciar secciones del informe
Código debe incluir comentarios explicando algoritmos
