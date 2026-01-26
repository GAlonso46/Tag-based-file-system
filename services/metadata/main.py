import os
import time
import socket
import grpc
import threading
import json
import random
import uuid
import logging
from concurrent import futures
from pathlib import Path
import fcntl
from sync_manager import SyncManager

# Ajusta imports según tu estructura
import protos.service_pb2 as pb2
import protos.service_pb2_grpc as pb2_grpc

# ================= CONFIGURACIÓN =================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Metadata] - %(message)s')
logger = logging.getLogger("MetadataService")

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "50051"))

DATA_DIR = Path("/app/metadata_storage")
DATA_DIR.mkdir(parents=True, exist_ok=True)

FILES_DB = DATA_DIR / "files_shared.json"

# N=3 en la teoría, pero el código se adapta a los que encuentre
REPLICATION_FACTOR = 2 

# ================= ESTADO GLOBAL =================

files_metadata = {}     # { file_id: { filename, owner_id, tags: [], replicas: [], ... } }
active_nodes = {}       # { node_id: { address, port, last_seen } }

active_nodes_lock = threading.Lock()
metadata_lock = threading.Lock()

current_lamport_time = 0
node_id = socket.gethostname() # Usado como ID único
sync_manager = SyncManager(node_id=node_id)

# ================= PERSISTENCIA =================

def load_state():
    global files_metadata
    if FILES_DB.exists():
        try:
            with open(FILES_DB, "r") as f:
                files_metadata = json.load(f)
            logger.info(f"Estado cargado: {len(files_metadata)} archivos.")
        except Exception as e:
            logger.error(f"Error cargando DB, iniciando vacío: {e}")
            files_metadata = {}
    else:
        files_metadata = {}

def save_state():
    with metadata_lock:
        try:
            tmp_file = FILES_DB.with_suffix(".tmp")
            with open(tmp_file, "w") as f:
                json.dump(files_metadata, f, indent=2)
            tmp_file.replace(FILES_DB)
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")

def save_state_locked(incoming_files=None):
    """
    Versión mejorada de save_state que usa locks de archivo 
    y comparación de versiones para evitar redundancia.
    """
    global files_metadata, current_lamport_time
    
    with metadata_lock:
        try:
            with open(FILES_DB, "r+") as f:
                # Bloqueo exclusivo del archivo
                fcntl.flock(f, fcntl.LOCK_EX)
                
                # Leer estado actual del disco
                disk_data = json.load(f) if os.path.getsize(FILES_DB) > 0 else {}
                
                changed = False
                # Si recibimos datos vía Gossip, comparamos versiones
                if incoming_files:
                    for fid, incoming_meta in incoming_files.items():
                        local_meta = disk_data.get(fid)
                        # Solo actualizar si la versión (lamport) es mayor
                        if not local_meta or incoming_meta['lamport_time'] > local_meta.get('lamport_time', -1):
                            disk_data[fid] = incoming_meta
                            changed = True
                else:
                    # Si es una escritura local (Commit/UpdateTags), usamos el estado en memoria
                    disk_data = files_metadata
                    changed = True

                if changed:
                    f.seek(0)
                    json.dump(disk_data, f, indent=2)
                    f.truncate()
                    files_metadata = disk_data # Sincronizar memoria con disco
                
                fcntl.flock(f, fcntl.LOCK_UN) # Liberar lock
        except Exception as e:
            logger.error(f"Error en persistencia segura: {e}")
# ================= HEARTBEATS (UDP) =================

MULTICAST_PORT = 5000

def heartbeat_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", MULTICAST_PORT))
    logger.info(f"Escuchando Heartbeats en puerto {MULTICAST_PORT}")

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            msg = data.decode().strip()
            parts = msg.split("|")
            if len(parts) >= 3:
                node_id, ip, port = parts[0], parts[1], int(parts[2])
                with active_nodes_lock:
                    active_nodes[node_id] = {
                        "address": ip, 
                        "port": port, 
                        "last_seen": time.time()
                    }
        except Exception as e:
            logger.error(f"Error en heartbeat: {e}")

def node_monitor():
    while True:
        time.sleep(5)
        now = time.time()
        dead = []
        with active_nodes_lock:
            for nid, info in active_nodes.items():
                if now - info["last_seen"] > 15:
                    dead.append(nid)
            for nid in dead:
                del active_nodes[nid]
                logger.warning(f"Nodo muerto eliminado: {nid}")

# ================= SERVICIO GRPC =================

class MetadataService(pb2_grpc.MetadataServiceServicer):

    pending_uploads = {}

    def AssignWrite(self, request, context):
        """Gateway solicita dónde escribir"""
        with active_nodes_lock:
            available = list(active_nodes.items())

        if not available:
            context.abort(grpc.StatusCode.UNAVAILABLE, "No hay DataNodes activos")

        # Seleccionar nodos aleatorios
        count = min(REPLICATION_FACTOR, len(available))
        selected = random.sample(available, count)
        
        file_id = str(uuid.uuid4())
        
        # Guardar intención temporalmente
        self.pending_uploads[file_id] = {
            "filename": request.filename,
            "tags": list(request.tags),
            "owner_id": request.owner_id,      # Importante: Gateway lo envía
            "mime_type": request.mime_type,    # Importante: Gateway lo envía
            "replicas_expected": [nid for nid, _ in selected]
        }

        resp = pb2.WriteAllocation(file_id=file_id)
        for nid, info in selected:
            resp.target_nodes.append(pb2.NodeInfo(
                node_id=nid, address=info["address"], port=info["port"]
            ))
        return resp

    def CommitWrite(self, request, context):
        global current_lamport_time
        if request.file_id not in self.pending_uploads:
            return pb2.CommitResponse(success=False)

        data = self.pending_uploads.pop(request.file_id)
        
        # Incrementar reloj Lamport local para nueva escritura
        current_lamport_time += 1

        meta_entry = {
            "filename": data["filename"],
            "size": request.size,
            "tags": data["tags"],
            "owner_id": data["owner_id"],
            "mime_type": data["mime_type"],
            "replicas": list(request.successful_nodes),
            "created_at": int(time.time()),
            "is_deleted": False,
            "lamport_time": current_lamport_time # Asignar versión
        }

        with metadata_lock:
            files_metadata[request.file_id] = meta_entry
        
        save_state_locked()
        # DISPARAR GOSSIP
        sync_manager.broadcast_update(request.file_id, meta_entry)
        
        return pb2.CommitResponse(success=True)

    def GossipPush(self, request, context):
        global current_lamport_time
        
        incoming_data = {}
        for f in request.files:
            incoming_data[f.file_id] = {
                "filename": f.filename,
                "size": f.size,
                "tags": list(f.tags),
                "owner_id": f.owner,
                "replicas": list(f.replicas),
                "created_at": f.created_at,
                "lamport_time": f.lamport_time,
                "is_deleted": False
            }
            # Sincronizar el reloj Lamport global (Max + 1)
            current_lamport_time = max(current_lamport_time, f.lamport_time)
        
        # Intentar persistir (la función save_state_locked filtrará si ya es viejo)
        save_state_locked(incoming_files=incoming_data)
        
        return pb2.GossipAck(ok=True, receiver_lamport_time=current_lamport_time)
    
    def LocateFile(self, request, context):
        """Gateway busca nodos para descargar"""
        fid = request.file_id
        if fid not in files_metadata or files_metadata[fid].get("is_deleted", False):
            context.abort(grpc.StatusCode.NOT_FOUND, "Archivo no encontrado o eliminado")

        meta = files_metadata[fid]
        
        resp = pb2.FileLocation(file_id=fid)
        resp.metadata.filename = meta["filename"]
        resp.metadata.size = meta["size"]
        resp.metadata.owner_id = meta.get("owner_id", "")
        resp.metadata.mime_type = meta.get("mime_type", "")
        resp.metadata.tags.extend(meta["tags"])
        
        # Solo devolver réplicas que sigan vivas
        with active_nodes_lock:
            for node_id in meta["replicas"]:
                if node_id in active_nodes:
                    info = active_nodes[node_id]
                    resp.replica_nodes.append(pb2.NodeInfo(
                        node_id=node_id, address=info["address"], port=info["port"]
                    ))

        return resp

    def ListFiles(self, request, context):
        """
        Lista archivos con FILTROS (Tags y Owner).
        Esto es crítico para que el Gateway muestre lo correcto.
        """
        resp = pb2.ListResponse()
        
        req_tags = set(request.tags_filter)
        req_owner = request.owner_filter

        for fid, meta in files_metadata.items():
            # 1. Ignorar eliminados
            if meta.get("is_deleted", False):
                continue

            # 2. Filtro de Owner (Si el Gateway lo pide)
            if req_owner and meta.get("owner_id") != req_owner:
                continue

            # 3. Filtro de Tags (Si hay tags solicitados)
            if req_tags:
                file_tags = set(meta.get("tags", []))
                # Si el archivo no tiene NINGUNO de los tags pedidos, saltar
                # (O lógica AND/OR según prefieras, usualmente es OR o "contiene alguno")
                if not req_tags.intersection(file_tags):
                    continue

            # Construir respuesta
            loc = pb2.FileLocation(file_id=fid)
            loc.metadata.filename = meta["filename"]
            loc.metadata.size = meta["size"]
            loc.metadata.owner_id = meta.get("owner_id", "")
            loc.metadata.mime_type = meta.get("mime_type", "")
            loc.metadata.created_at = meta.get("created_at", 0)
            loc.metadata.tags.extend(meta.get("tags", []))
            
            resp.files.append(loc)

        return resp

    def DeleteFile(self, request, context):
        """Implementación de Soft Delete con propagación Gossip"""
        global current_lamport_time
        fid = request.file_id
        
        with metadata_lock:
            if fid not in files_metadata:
                context.abort(grpc.StatusCode.NOT_FOUND, "Archivo no existe")
            
            # 1. Incrementar versión lógica
            current_lamport_time += 1
            
            # 2. Marcar como borrado y actualizar versión
            files_metadata[fid]["is_deleted"] = True
            files_metadata[fid]["lamport_time"] = current_lamport_time
            
            meta_to_sync = files_metadata[fid]
        
        # 3. Persistencia segura con Lock
        save_state_locked()
        
        # 4. Propagar el "Tombstone" (lápida) a los demás nodos
        sync_manager.broadcast_update(fid, meta_to_sync)
        
        logger.info(f"Archivo eliminado (soft) y propagado: {fid} (v.{current_lamport_time})")
        return pb2.DeleteResponse(success=True)

    def UpdateTags(self, request, context):
        """Actualizar etiquetas con propagación Gossip"""
        global current_lamport_time
        fid = request.file_id
        new_tags = list(request.tags)

        with metadata_lock:
            if fid not in files_metadata:
                context.abort(grpc.StatusCode.NOT_FOUND, "Archivo no existe")
            
            # 1. Incrementar versión lógica
            current_lamport_time += 1
            
            # 2. Actualizar datos y versión
            files_metadata[fid]["tags"] = new_tags
            files_metadata[fid]["lamport_time"] = current_lamport_time
            
            meta_to_sync = files_metadata[fid]
        
        # 3. Persistencia segura con Lock
        save_state_locked()
        
        # 4. Propagar actualización a la red
        sync_manager.broadcast_update(fid, meta_to_sync)
        
        logger.info(f"Tags actualizados y propagados para {fid}: {new_tags} (v.{current_lamport_time})")
        return pb2.TagResponse(success=True, current_tags=new_tags)
    
# ================= ARRANQUE =================

def serve():
    load_state()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_MetadataServiceServicer_to_server(MetadataService(), server)
    server.add_insecure_port(f"[::]:{PORT}")

    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()

    logger.info(f"Metadata AP Service iniciado en puerto {PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()