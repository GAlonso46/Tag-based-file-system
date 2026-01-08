# Mejoras de Implementación - TagFS Distributed System

Este documento describe las mejoras implementadas para alcanzar 100% de cumplimiento con `informe_sd.md`.

## 🎯 Mejoras Implementadas

### 1. ✅ Re-replicación Automática

**Archivo:** `services/metadata/main.py`

**Funcionalidad:**
- Detecta cuando un DataNode falla (no envía heartbeats por >10 segundos)
- Identifica automáticamente todos los archivos afectados
- Selecciona un DataNode sano como origen y uno disponible como destino
- Ejecuta la transferencia Pull: el destino copia los datos desde el origen
- Actualiza los metadatos para reflejar la nueva ubicación
- Mantiene el factor de replicación N=3

**Logs para verificar:**
```
[Metadata] DataNode {id} is dead, removing
[Re-replication] Scanning files affected by dead node {id}
[Re-replication] Found X files to re-replicate
[Re-replication] Replicating {filename} from {source} to {target}
[Re-replication] ✓ Successfully replicated {filename} to {target}
```

### 2. ✅ Uploads Paralelos (Gateway)

**Archivo:** `services/gateway/main.py`

**Funcionalidad:**
- Usa `asyncio` y `ThreadPoolExecutor` para uploads concurrentes
- Sube archivos a los 3 DataNodes simultáneamente (no secuencialmente)
- Reduce tiempo de upload en ~66% para archivos grandes
- Mantiene el Quorum W=2 (mínimo 2 escrituras exitosas)

**Mejora de rendimiento:**
- **Antes:** 3 DataNodes × 10s = 30s total
- **Ahora:** max(10s, 10s, 10s) = 10s total

### 3. ✅ Manejo de Errores Mejorado

**Archivo:** `services/gateway/main.py`

**Funcionalidad:**
- Reintentos automáticos con backoff exponencial
- Maneja múltiples tipos de errores gRPC:
  - `FAILED_PRECONDITION`: Nodo no es líder
  - `UNAVAILABLE`: Nodo temporalmente caído
  - `DEADLINE_EXCEEDED`: Timeout
- Máximo 5 intentos antes de fallar
- Rotación automática entre réplicas de Metadata Service

**Backoff exponencial:**
- Intento 1: 0.5s
- Intento 2: 1.0s
- Intento 3: 2.0s
- Intento 4: 4.0s
- Intento 5: 8.0s

### 4. ✅ Soporte TLS Opcional

**Archivos modificados:**
- `services/gateway/main.py`
- `services/metadata/main.py`
- `services/datanode/main.py`
- `generate_certs.sh` (nuevo)

**Funcionalidad:**
- Cifrado TLS 1.2+ para todas las conexiones gRPC
- Autenticación mutua (mTLS) entre servicios
- Certificados autofirmados para desarrollo
- Fallback automático a conexiones inseguras si TLS falla

## 🚀 Cómo Usar

### Modo Inseguro (Desarrollo - Por Defecto)

Sin cambios necesarios, todo funciona como antes:

```bash
docker stack deploy -c docker-stack-distributed.yml tagfs
```

### Modo TLS (Seguro - Recomendado para Producción)

#### Paso 1: Generar Certificados

```bash
./generate_certs.sh
```

Esto crea el directorio `./certs` con:
- `ca-cert.pem`: Certificado de la CA
- `ca-key.pem`: Clave privada de la CA
- `server-cert.pem`: Certificado del servidor
- `server-key.pem`: Clave privada del servidor
- `client-cert.pem`: Certificado del cliente
- `client-key.pem`: Clave privada del cliente

#### Paso 2: Desplegar con TLS Habilitado

Edita `docker-stack-distributed.yml` y agrega a cada servicio:

```yaml
services:
  gateway:
    environment:
      - ENABLE_TLS=true
      - CERT_DIR=/app/certs
    volumes:
      - ./certs:/app/certs:ro
  
  metadata:
    environment:
      - ENABLE_TLS=true
      - CERT_DIR=/app/certs
    volumes:
      - ./certs:/app/certs:ro
  
  data-node:
    environment:
      - ENABLE_TLS=true
      - CERT_DIR=/app/certs
    volumes:
      - ./certs:/app/certs:ro
```

Luego despliega:

```bash
docker stack deploy -c docker-stack-distributed.yml tagfs
```

#### Paso 3: Verificar TLS

Revisa los logs para confirmar:

```bash
docker service logs tagfs_gateway 2>&1 | grep TLS
docker service logs tagfs_metadata 2>&1 | grep TLS
docker service logs tagfs_data-node 2>&1 | grep TLS
```

Deberías ver:
```
[Gateway] TLS enabled for gRPC connections
[Metadata] TLS enabled on port 50051
[datanode-...] TLS enabled on port 50051
```

## 🧪 Probar Re-replicación

### Escenario de Prueba

1. **Sube un archivo:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@testfile.txt" \
  -F "tags=test,important"
```

2. **Verifica las réplicas:**
```bash
# En los logs del Metadata Service verás algo como:
[Metadata] Committed file testfile.txt (uuid-123) with replicas: [node1, node2, node3]
```

3. **Simula fallo de un DataNode:**
```bash
# Obtén el ID del contenedor de un DataNode
docker ps | grep data-node

# Detén uno de los DataNodes
docker stop CONTAINER_ID
```

4. **Observa la re-replicación automática:**
```bash
docker service logs tagfs_metadata --follow
```

Verás algo como:
```
[Metadata] DataNode node1 is dead, removing
[Re-replication] Scanning files affected by dead node node1
[Re-replication] Found 1 files to re-replicate
[Re-replication] Replicating testfile.txt from node2 to node4
[Re-replication] ✓ Successfully replicated testfile.txt to node4
[Re-replication] Re-replication round complete for dead node node1
```

5. **Verifica que el archivo sigue disponible:**
```bash
curl -X GET "http://localhost:8000/files/FILE_ID" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -o downloaded.txt
```

## 📊 Métricas y Monitoreo

### Quorum Writes (W=2)

El Gateway garantiza que cada archivo se escribe en al menos 2 de 3 DataNodes:

```python
required_writes = min(2, len(target_nodes))  # W=2
if success_count < required_writes:
    raise HTTPException(500, "Write quorum not met")
```

### Quorum Reads (R=2)

Al descargar, el Gateway consulta 2 réplicas y selecciona la versión más reciente:

```python
READ_QUORUM = 2
read_quorum = min(READ_QUORUM, len(loc.replica_nodes))
nodes_to_query = random.sample(loc.replica_nodes, read_quorum)
```

### Garantía de Consistencia

**R + W > N → 2 + 2 > 3** ✅

Esto asegura que:
- Cualquier lectura obtiene la última escritura
- No hay ventanas de inconsistencia
- Se detectan automáticamente versiones obsoletas

## 🔒 Seguridad

### Autenticación

- **JWT Tokens:** Autenticación sin estado
- **Expiración:** 30 minutos (configurable en `api/dependencies.py`)
- **Algoritmo:** HS256 con clave secreta

### Autorización

- Usuarios solo ven sus propios archivos
- Usuarios admin pueden ver todos los archivos
- Operaciones de escritura requieren autenticación válida

### Cifrado (cuando TLS está habilitado)

- **En tránsito:** TLS 1.2+ para todas las conexiones gRPC
- **Autenticación mutua:** Certificados cliente y servidor
- **Algoritmos:** RSA 4096-bit, SHA-256

## ⚠️ Notas Importantes

### Limitaciones Actuales

1. **UDP Heartbeats no cifrados:** Por diseño para mantener overhead bajo
2. **Certificados autofirmados:** Para desarrollo, usar CA real en producción
3. **Re-replicación Pull:** Implementada, pero podría optimizarse con Push-Pull híbrido

### Configuración Recomendada para Producción

```bash
# En cada servicio, configura:
ENABLE_TLS=true
CERT_DIR=/etc/tagfs/certs
SECRET_KEY=<genera-clave-segura-de-256-bits>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Monitoreo de Salud

Endpoints de health check:

- **Gateway:** `GET http://localhost:8000/`
- **Metadata:** Verifica logs de Bully election
- **DataNode:** Verifica heartbeats en logs de Metadata

## 🎯 Cumplimiento del Informe

| Requisito | Estado | Implementación |
|-----------|--------|----------------|
| Re-replicación automática | ✅ 100% | `trigger_re_replication()` en Metadata |
| Uploads paralelos | ✅ 100% | `asyncio.gather()` en Gateway |
| Retry con backoff | ✅ 100% | `call_metadata_with_leader_retry()` |
| TLS opcional | ✅ 100% | Configuración en todos los servicios |
| Quorum N=3, W=2, R=2 | ✅ 100% | Validación en upload/download |
| Detección de fallos | ✅ 100% | Heartbeat monitor + 10s timeout |

### Cumplimiento Total: **100%** 🎉

---

## 📝 Cambios en Archivos

### Modificados
- `services/gateway/main.py`: Parallelización + TLS + retry mejorado
- `services/metadata/main.py`: Re-replicación + TLS
- `services/datanode/main.py`: TLS
- `protos/service.proto`: Mensajes de replicación

### Nuevos
- `generate_certs.sh`: Script de generación de certificados
- `IMPLEMENTATION_IMPROVEMENTS.md`: Este archivo

---

**Última actualización:** 14 de Diciembre de 2025
