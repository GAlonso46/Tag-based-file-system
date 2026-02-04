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

# Garantizar existencia del archivo
if not FILES_DB.exists():
    with open(FILES_DB, "w") as f:
        json.dump({}, f)

# N=3 en la teoría, pero el código se adapta a los que encuentre
REPLICATION_FACTOR = 2 

# ================= ESTADO GLOBAL =================

files_metadata = {}     # { file_id: { filename, owner_id, tags: [], replicas: [], ... } }
active_nodes = {}       # { node_id: { address, port, last_seen } }

active_nodes_lock = threading.Lock()
metadata_lock = threading.Lock()

# Queue para persistencia asíncrona (evita bloqueos en CommitWrite)
import queue
persistence_queue = queue.Queue(maxsize=100)

current_lamport_time = 0
node_id = socket.gethostname() # Usado como ID único
sync_manager = SyncManager(node_id=node_id)

# Tiempo en que el contenedor de Metadata inició (en segundos)
METADATA_START_TIME = time.time()

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

def save_state_async():
    """
    Persistencia asíncrona: Adquiere lock, copia estado y encola.
    Usar ESTA función si NO tienes el lock.
    """
    global files_metadata
    with metadata_lock:
        snapshot = files_metadata.copy()
    persistence_queue.put(snapshot)

def queue_snapshot_no_lock():
    """
    Persistencia asíncrona: Asume que YA tienes el lock.
    Solo hace copy y put.
    """
    global files_metadata
    # ASUMIMOS QUE EL CALLER TIENE EL LOCK
    snapshot = files_metadata.copy()
    persistence_queue.put(snapshot)

def persistence_worker():
    """
    Thread dedicado que escribe a disco sin bloquear requests.
    """
    logger.info("[Persistence] Worker thread iniciado")
    
    while True:
        try:
            snapshot = persistence_queue.get(timeout=5)
            try:
                tmp_file = FILES_DB.with_suffix(".tmp")
                with open(tmp_file, "w") as f:
                    json.dump(snapshot, f, indent=2)
                tmp_file.replace(FILES_DB)
                logger.debug(f"[Persistence] Guardado {len(snapshot)} archivos")
            except Exception as e:
                logger.error(f"[Persistence] Error escribiendo: {e}")
            persistence_queue.task_done()
        except Exception:
            pass

def save_state_locked(incoming_files=None):
    """
    LEGACY: Ahora solo mezcla incoming y llama a persistencia.
    NO adquiere lock para persistencia si ya lo tenemos (evita deadlock).
    """
    global files_metadata
    
    # Esta función se llama históricamente "locked" porque antes bloqueaba disco.
    # Ahora solo gestiona merge de estado.
    
    # El caller responsable de llamar aqui debe saber si tiene el lock o no.
    # Pero para no romper compatibilidad, asumimos que save_state_locked se llama
    # DESDE LUGARES QUE YA TIENEN EL LOCK (como process_gossip_update).
    
    if incoming_files:
        # LOGGING DETALLADO SOLICITADO
        logger.info(f"[Merge] Procesando lote de {len(incoming_files)} archivos externos")

        # ASUMIMOS QUE TENEMOS EL LOCK para modificar files_metadata
        for fid, incoming_meta in incoming_files.items():
            local_meta = files_metadata.get(fid)
            
            incoming_ver = incoming_meta.get('lamport_time', 0)
            
            # 1. Archivo Nuevo
            if not local_meta:
                logger.info(f"[Merge] > NUEVO: {fid} (v.{incoming_ver})")
                files_metadata[fid] = incoming_meta
                continue

            local_ver = local_meta.get('lamport_time', 0)

            # 2. Versión Mayor (Update Standard)
            if incoming_ver > local_ver:
                logger.info(f"[Merge] > UPDATE: {fid} v.{local_ver} -> v.{incoming_ver}")
                files_metadata[fid] = incoming_meta
            
            # 3. Empate (CONFLICTO) - AQUI ESTABA EL BUG
            elif incoming_ver == local_ver:
                # Politica: Delete Wins (Si uno dice borrado y el otro no, gana borrado)
                incoming_deleted = incoming_meta.get("is_deleted", False)
                local_deleted = local_meta.get("is_deleted", False)
                
                if incoming_deleted and not local_deleted:
                    logger.warning(f"[Merge] > CONFLICTO ({fid}): Empate v.{local_ver}. GANA DELETE EXTERNO.")
                    files_metadata[fid] = incoming_meta
                elif not incoming_deleted and local_deleted:
                     logger.info(f"[Merge] . Ignorando Alive vs Delete local (Gana Delete local)")
                else:
                     logger.debug(f"[Merge] . Idénticos v.{local_ver}")

            # 4. Versión Menor (Stale)
            else:
                logger.debug(f"[Merge] x OLD: {fid} v.{incoming_ver} < v.{local_ver}")
    
    # IMPORTANTE: save_state_locked suele llamarse dentro de un bloque 'with metadata_lock'
    # Por tanto, debemos usar la versión SIN LOCK.
    queue_snapshot_no_lock()
# ================= HEARTBEATS (UDP) =================

MULTICAST_PORT = 5000

def heartbeat_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", MULTICAST_PORT))
    logger.info(f"Escuchando Heartbeats + Reportes en puerto {MULTICAST_PORT}")

    while True:
        try:
            data, _ = sock.recvfrom(4096) # Aumentamos buffer por seguridad
            msg = data.decode().strip()
            parts = msg.split("|")
            
            if len(parts) >= 3:
                # Formato básico: ID|IP|PORT|LOAD
                n_id, ip, port = parts[0], parts[1], int(parts[2])
                
                # Actualizar estado "VIVO"
                with active_nodes_lock:
                    active_nodes[n_id] = {
                        "address": ip, 
                        "port": port, 
                        "last_seen": time.time()
                    }
                
                # Formato Extendido: ID|IP|PORT|LOAD|FILE1,FILE2...
                if len(parts) >= 5:
                    files_str = parts[4]
                    # Si viene vacío (ej: "file1,,file2"), filter limpia
                    reported_files = [f for f in files_str.split(",") if f]
                    
                    # Llamamos a la reconciliación en un hilo aparte para no bloquear el listener UDP
                    # (Importante para no perder paquetes de otros nodos)
                    threading.Thread(
                        target=reconcile_node_files,
                        args=(n_id, ip, port, reported_files),
                        daemon=True
                    ).start()

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
        t0 = time.time()
        logger.info(f"AssignWrite request for {request.filename}")
        
        with active_nodes_lock:
            available = list(active_nodes.items())
        
        if not available:
            context.abort(grpc.StatusCode.UNAVAILABLE, "No hay DataNodes activos")

        # Seleccionar nodos aleatorios
        count = min(REPLICATION_FACTOR, len(available))
        selected = random.sample(available, count)
        
        file_id = str(uuid.uuid4())
        
        # Datos de la intención
        pending_data = {
            "file_id": file_id,
            "filename": request.filename,
            "tags": list(request.tags),
            "owner_id": request.owner_id,
            "mime_type": request.mime_type,
            "replicas_expected": [nid for nid, _ in selected]
        }
        
        # Guardar intención LOCALMENTE
        self.pending_uploads[file_id] = pending_data

        # REPLICAR intención a otros nodos (Best effort async)
        # Esto permite que CommitWrite vaya a otro nodo si el load balancer lo decide
        sync_manager.broadcast_pending(pending_data)

        resp = pb2.WriteAllocation(file_id=file_id)
        for nid, info in selected:
            resp.target_nodes.append(pb2.NodeInfo(
                node_id=nid, address=info["address"], port=info["port"]
            ))
        
        logger.info(f"AssignWrite allocated {file_id} to {[nid for nid, _ in selected]} in {time.time() - t0:.4f}s")
        return resp

    def PropagatePending(self, request, context):
        """RPC para recibir una intención de escritura de otro nodo"""
        logger.info(f"Recibida intención PendingUpload: {request.file_id}")
        self.pending_uploads[request.file_id] = {
            "filename": request.filename,
            "tags": list(request.tags),
            "owner_id": request.owner_id,
            "mime_type": request.mime_type,
            "replicas_expected": list(request.replicas_expected)
        }
        return pb2.GossipAck(ok=True)

    def CommitWrite(self, request, context):
        global current_lamport_time
        t0 = time.time()
        logger.info(f"CommitWrite request for {request.file_id}")
        
        if request.file_id not in self.pending_uploads:
            logger.warning(f"CommitWrite failed: {request.file_id} not in pending_uploads")
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

        t_lock = time.time()
        with metadata_lock:
            lock_duration = time.time() - t_lock
            files_metadata[request.file_id] = meta_entry
        
        # Sincronización
        t_persist = time.time()
        # Usamos save_state_async (con lock) porque YA NO tenemos el lock aquí
        save_state_async()
        persist_time = time.time() - t_persist
        
        t_gossip = time.time()
        sync_manager.broadcast_update(request.file_id, meta_entry)
        gossip_time = time.time() - t_gossip
        
        total_time = time.time() - t0
        logger.info(f"CommitWrite {request.file_id} finished in {total_time:.4f}s (Lock: {lock_duration:.4f}s, Persist: {persist_time:.4f}s, Gossip: {gossip_time:.4f}s)")
        
        return pb2.CommitResponse(success=True)

    def GossipPull(self, request, context):
        """Servidor: Entrega toda la DB local al solicitante"""
        logger.info(f"Recibida solicitud GossipPull del nodo {request.requester_id}")
        
        entries = []
        with metadata_lock:
            for fid, meta in files_metadata.items():
                # USO DE .get() PARA EVITAR KEYERRORS EN DATOS ANTIGUOS
                entries.append(pb2.FileMetadataEntry(
                    file_id=fid,
                    filename=meta.get('filename', "unknown"),
                    tags=meta.get('tags', []),
                    owner=meta.get('owner_id', ""),  
                    size=meta.get('size', 0),
                    replicas=meta.get('replicas', []),
                    created_at=meta.get('created_at', 0),
                    lamport_time=meta.get('lamport_time', 0),
                    is_deleted=meta.get('is_deleted', False)
                ))
        
        return pb2.GossipUpdate(
            sender_id=int(hash(node_id) % 10**8),
            sender_lamport_time=current_lamport_time,
            files=entries
        )

    def process_gossip_update(self, update):
        """Procesa una actualización (sea por Push o por Pull)"""
        global current_lamport_time
        incoming_data = {}
        for f in update.files:
            incoming_data[f.file_id] = {
                "filename": f.filename,
                "size": f.size,
                "tags": list(f.tags),
                "owner_id": f.owner,
                "replicas": list(f.replicas),
                "created_at": f.created_at,
                "lamport_time": f.lamport_time,
                "is_deleted": f.is_deleted
            }
            current_lamport_time = max(current_lamport_time, f.lamport_time)
        
        save_state_locked(incoming_files=incoming_data)

    def GossipPush(self, request, context):
        """Reutiliza la lógica de procesamiento común"""
        self.process_gossip_update(request)
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

# ================= AUTO-HEALING (RE-REPLICACIÓN) =================
def discover_datanode_ips():
    """
    Descubre dinámicamente todas las IPs asociadas al alias datanode_service.
    """
    try:
        results = socket.getaddrinfo(
            "datanode_service",
            0,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM
        )

        ips = set()
        for r in results:
            ips.add(r[4][0])

        return list(ips)

    except Exception as e:
        logger.error(f"No se pudieron descubrir DataNodes vía DNS: {e}")
        return []

def replication_loop(service_instance):
    """
    Auto-healing basado en Heartbeats.
    Replica archivos que tengan menos copias que REPLICATION_FACTOR.
    """

    logger.info("Iniciando monitor de auto-sanación (Replication Monitor)...")

    while True:
        time.sleep(10)

        # ==============================
        # 1. Snapshot consistente
        # ==============================
        with metadata_lock:
            all_files = list(files_metadata.items())

        with active_nodes_lock:
            active_snapshot = active_nodes.copy()

        if not active_snapshot:
            logger.warning("No hay DataNodes activos según heartbeats. Reintentando luego...")
            continue

        jobs = []

        # ==============================
        # 2. Analizar archivos
        # ==============================
        for fid, meta in all_files:

            if meta.get("is_deleted", False):
                continue

            current_replicas = meta.get("replicas", [])

            # Réplicas que están vivas
            alive_replicas = [
                n for n in current_replicas
                if n in active_snapshot
            ]

            # Debe existir al menos una copia viva
            if not alive_replicas:
                continue

            # Ya cumple el factor
            if len(alive_replicas) >= REPLICATION_FACTOR:
                continue

            # ==============================
            # 3. Seleccionar candidatos
            # ==============================
            candidates = [
                node_id
                for node_id in active_snapshot.keys()
                if node_id not in current_replicas
            ]

            if not candidates:
                continue

            target_node = random.choice(candidates)
            source_node = random.choice(alive_replicas)

            jobs.append({
                "file_id": fid,
                "target": target_node,
                "source": source_node,
                "target_info": active_snapshot[target_node],
                "source_info": active_snapshot[source_node]
            })

        # ==============================
        # 4. Ejecutar reparaciones
        # ==============================
        for job in jobs:

            fid = job["file_id"]
            tgt_id = job["target"]
            src_id = job["source"]
            tgt_info = job["target_info"]
            src_info = job["source_info"]

            logger.info(f"Replicando {fid}: {src_id} -> {tgt_id}")

            try:
                channel = grpc.insecure_channel(
                    f"{tgt_info['address']}:{tgt_info['port']}"
                )

                stub = pb2_grpc.DataNodeServiceStub(channel)

                req = pb2.ReplicationRequest(
                    file_id=fid,
                    source_node_address=src_info["address"],
                    source_node_port=src_info["port"]
                )

                resp = stub.ReplicateFrom(req, timeout=300)
                channel.close()

                if resp.success:

                    global current_lamport_time

                    with metadata_lock:
                        if fid in files_metadata:
                            files_metadata[fid]["replicas"].append(tgt_id)
                            current_lamport_time += 1
                            files_metadata[fid]["lamport_time"] = current_lamport_time
                            updated_meta = files_metadata[fid]

                            save_state_locked()
                            sync_manager.broadcast_update(fid, updated_meta)

                    logger.info(f"Reparación exitosa para {fid} en {tgt_id}")

            except Exception as e:
                logger.error(f"Fallo reparando {fid}: {e}")

def reconcile_node_files(node_id, node_ip, node_port, reported_files):
    """
    Compara lo que el DataNode dice tener vs lo que el Metadata cree que tiene.
    """
    # Convertimos la lista del reporte a un Set para búsqueda rápida
    reported_set = set(reported_files)
    
    files_to_delete_physically = []

    # Tiempo que lleva vivo este Metadata
    uptime_seconds = time.time() - METADATA_START_TIME
    # Definimos periodo de gracia
    GRACE_PERIOD = 180
    
    with metadata_lock:
        for fid in reported_files:
            if fid == "": continue # Ignorar strings vacíos
            
            # El archivo existe en DB pero está marcado como eliminado.
            if (fid in files_metadata) and (files_metadata[fid].get("is_deleted", False)):
                files_to_delete_physically.append(fid)

            # El archivo NO existe en nuestra DB.
            elif fid not in files_metadata:
                # Solo borramos si ya pasó el periodo de gracia de sincronización inicial
                if uptime_seconds > GRACE_PERIOD:
                    logger.info(f"Limpieza de archivo huérfano: {fid} no existe en DB tras uptime de {int(uptime_seconds)}s.")
                    files_to_delete_physically.append(fid)
                else:
                    # Estamos en periodo de gracia, ignoramos para evitar falsos positivos
                    pass    

    # Ejecutar borrado físico (RPC hacia el DataNode)
    if files_to_delete_physically:
        logger.warning(f"Detectados {len(files_to_delete_physically)} archivos fantasmas en {node_id}. Ordenando eliminación...")
        try:
            channel = grpc.insecure_channel(f"{node_ip}:{node_port}")
            stub = pb2_grpc.DataNodeServiceStub(channel)
            for fid in files_to_delete_physically:
                try:
                    stub.DeleteFile(pb2.FileRequest(file_id=fid), timeout=1)
                except Exception as e:
                    logger.error(f"Error borrando fantasma {fid} en {node_id}: {e}")
            channel.close()
        except Exception as e:
            logger.error(f"No se pudo conectar a {node_id} para limpieza: {e}")

    # 2. Detectar Archivos Perdidos (Metadata cree que está, pero el nodo NO lo reportó)
    #    Recorremos TODA la metadata buscando referencias a este nodo
    #    (Esta operación puede ser pesada si hay millones de archivos, para <100 es instantánea)
    
    with metadata_lock:
        for fid, meta in files_metadata.items():
            if meta.get("is_deleted", False):
                continue
            
            # Si el nodo está en la lista de réplicas...
            if node_id in meta["replicas"]:
                # ...pero NO reportó tener el archivo
                if fid not in reported_set:
                    logger.warning(f"Inconsistencia: {node_id} perdió el archivo {fid}. Actualizando registro.")
                    # Lo sacamos de la lista de réplicas
                    meta["replicas"].remove(node_id)
                    # Al sacarlo, el 'replication_loop' detectará automáticamente 
                    # que faltan copias y creará una nueva en otro nodo.                

# ================= ARRANQUE =================

def serve():
    load_state()
    service_instance = MetadataService() 
    
    # Aumentamos workers a 100 para evitar saturación
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    pb2_grpc.add_MetadataServiceServicer_to_server(service_instance, server)
    server.add_insecure_port(f"[::]:{PORT}")

    # 1. Hilos iniciales
    threading.Thread(target=heartbeat_listener, daemon=True).start()
    threading.Thread(target=node_monitor, daemon=True).start()
    
    # 2. Persistence worker (NUEVO - evita bloqueos)
    threading.Thread(target=persistence_worker, daemon=True).start()

    # 3. Hilo de Sincronización Periódica
    threading.Thread(target=sync_manager.periodic_sync_loop, args=(service_instance,), daemon=True).start()
    
    # 4. Hilo de Auto-Healing
    threading.Thread(target=replication_loop, args=(service_instance,), daemon=True).start()

    # 5. Intentar un Pull inicial inmediatamente al arrancar
    def initial_sync():
        time.sleep(5) # Esperar a que otros nodos estén listos
        logger.info("Ejecutando sincronización inicial (Cold Start)...")
        resp = sync_manager.request_pull_sync()
        if resp:
            service_instance.process_gossip_update(resp)

    threading.Thread(target=initial_sync, daemon=True).start()

    logger.info(f"Metadata Service iniciado con Gossip Pull/Push en {PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()