# Suite de Tests - TagFS Distributed System

Esta carpeta contiene tests automatizados para verificar todas las funcionalidades implementadas del sistema de ficheros distribuido.

## 📋 Tests Disponibles

### 1. `verify_improvements.sh`
**Verificación estática de implementación**

Verifica que todos los componentes estén correctamente implementados sin necesidad de desplegar el sistema:

- ✅ Archivos modificados existentes
- ✅ Función `trigger_re_replication()` implementada
- ✅ Uploads paralelos con `asyncio.gather()`
- ✅ Retry logic con backoff exponencial
- ✅ Soporte TLS en todos los servicios
- ✅ Script de generación de certificados
- ✅ Configuración de Quorum N=3, W=2, R=2
- ✅ Documentación actualizada

**Uso:**
```bash
./verify_improvements.sh
```

**Duración:** ~5 segundos

---

### 2. `test_parallel_upload.sh`
**Test de uploads paralelos y Quorum**

Verifica el funcionamiento de:

- ✅ Uploads concurrentes a múltiples DataNodes
- ✅ Quorum Write (W=2) - mínimo 2 réplicas exitosas
- ✅ Quorum Read (R=2) - consulta a 2 réplicas
- ✅ Integridad de datos (verificación MD5)
- ✅ Medición de rendimiento

**Requisitos:**
- Stack desplegado y corriendo
- Usuario de test creado automáticamente

**Uso:**
```bash
# Asegúrate de que el stack esté corriendo
docker stack deploy -c docker-stack-distributed.yml tagfs

# Ejecuta el test
./test_parallel_upload.sh
```

**Duración:** ~30 segundos

**Qué hace:**
1. Crea usuario de prueba
2. Genera archivo de 5MB
3. Mide tiempo de upload
4. Verifica réplicas en metadata
5. Descarga y valida integridad
6. Compara rendimiento

---

### 3. `test_rereplica.sh`
**Test de re-replicación automática**

Verifica el funcionamiento completo del sistema de tolerancia a fallas:

- ✅ Detección de nodos caídos (<15 segundos)
- ✅ Activación automática de re-replicación
- ✅ Transferencia Pull entre DataNodes
- ✅ Actualización de metadatos
- ✅ Disponibilidad continua del archivo
- ✅ Restauración del factor N=3

**Requisitos:**
- Stack desplegado con al menos 3 DataNodes
- Permiso para detener/reiniciar contenedores

**Uso:**
```bash
./test_rereplica.sh
```

**Duración:** ~60 segundos

**Qué hace:**
1. Sube archivo de prueba
2. Verifica réplicas iniciales (N=3)
3. Simula fallo deteniendo un DataNode
4. Espera detección de fallo (T2=10s)
5. Verifica activación de re-replicación
6. Confirma disponibilidad del archivo
7. Valida integridad de datos
8. Reinicia el DataNode detenido

---

### 4. `run_all_tests.sh`
**Suite completa de tests**

Ejecuta todos los tests en secuencia con manejo de errores y reporte consolidado.

**Uso:**
```bash
./run_all_tests.sh
```

**Duración:** ~2-3 minutos

**Características:**
- Verificación de prerequisitos
- Opción de auto-deployment del stack
- Ejecución secuencial con confirmaciones
- Reporte consolidado de resultados
- Menú interactivo post-test

---

## 🚀 Inicio Rápido

### Opción 1: Test Rápido (Sin deployment)

```bash
# Solo verificación estática
./verify_improvements.sh
```

### Opción 2: Tests Completos

```bash
# Construir imágenes (primera vez)
./build-images.sh

# Ejecutar suite completa (incluye deployment)
./run_all_tests.sh
```

### Opción 3: Tests Individuales

```bash
# 1. Desplegar stack
docker stack deploy -c docker-stack-distributed.yml tagfs

# Esperar a que los servicios inicien
sleep 30

# 2. Ejecutar tests específicos
./test_parallel_upload.sh
./test_rereplica.sh
```

---

## 📊 Interpretación de Resultados

### Test de Uploads Paralelos

**Exitoso si:**
- ✅ HTTP 200 en upload y download
- ✅ Al menos 2 réplicas creadas (W=2)
- ✅ MD5 del archivo original == MD5 descargado
- ✅ Tiempo de upload razonable (<30s para 5MB en LAN)

**Logs esperados:**
```
✓ Upload de 5MB completado en X.XXs
✓ Quorum Write W=2 verificado (3 réplicas)
✓ Descarga y verificación exitosa
✓ Integridad de datos confirmada (MD5)
```

### Test de Re-replicación

**Exitoso si:**
- ✅ Sistema detecta nodo caído en <15 segundos
- ✅ Logs muestran: "Re-replication" y "Successfully replicated"
- ✅ Archivo sigue disponible tras fallo
- ✅ Contenido intacto (diff exitoso)

**Logs esperados en Metadata:**
```
[Metadata] DataNode node-xxx is dead, removing
[Re-replication] Scanning files affected by dead node
[Re-replication] Found X files to re-replicate
[Re-replication] Replicating file.txt from node-A to node-B
[Re-replication] ✓ Successfully replicated file.txt to node-B
```

---

## 🔍 Troubleshooting

### Error: "Stack tagfs no está corriendo"

**Solución:**
```bash
docker stack deploy -c docker-stack-distributed.yml tagfs
sleep 30  # Esperar a que los servicios inicien
```

### Error: "No se pudo autenticar"

**Causa:** Gateway no está listo o hay problemas de red

**Solución:**
```bash
# Verificar estado del Gateway
docker service ls | grep gateway

# Ver logs
docker service logs tagfs_gateway --tail 50

# Esperar más tiempo
sleep 10
```

### Error: "No hay suficientes DataNodes"

**Causa:** No hay al menos 3 DataNodes corriendo

**Solución:**
```bash
# Verificar cuántos DataNodes hay
docker ps | grep data-node

# Escalar DataNodes si es necesario
docker service scale tagfs_data-node=3
sleep 20
```

### Re-replicación no se activa

**Posibles causas:**
1. Timeout muy corto (esperar al menos 15s)
2. No hay otros DataNodes disponibles
3. Archivo no tenía réplica en el nodo caído

**Verificación:**
```bash
# Ver logs completos
docker service logs tagfs_metadata --follow

# Verificar DataNodes activos
docker ps --filter "name=tagfs_data-node"
```

---

## 📈 Métricas de Rendimiento

### Uploads Paralelos

**Mejora esperada:** ~60-70% más rápido que secuencial

| Escenario | Tiempo Estimado |
|-----------|-----------------|
| Secuencial (3 nodos × 5s) | ~15s |
| Paralelo (max de 3 × 5s) | ~5-6s |
| **Mejora** | **~66%** |

### Re-replicación

**Tiempos críticos:**

| Evento | Tiempo |
|--------|--------|
| Detección de fallo | <15s |
| Inicio de re-replicación | <20s |
| Transferencia (5MB) | ~5-10s |
| **Total** | **<35s** |

---

## 🎯 Criterios de Éxito

Para considerar el sistema **100% funcional**, todos los tests deben pasar:

- [x] `verify_improvements.sh` → ✅ Sin errores
- [x] `test_parallel_upload.sh` → ✅ Quorum verificado + MD5 correcto
- [x] `test_rereplica.sh` → ✅ Re-replicación exitosa + datos íntegros

**Estado objetivo:**
```
Tests ejecutados: 3
Tests pasados:   3
Tests fallados:  0

✓ TODOS LOS TESTS PASARON ✓✓✓
Sistema listo para producción 🚀
```

---

## 📝 Logs Útiles

### Ver logs de re-replicación

```bash
docker service logs tagfs_metadata 2>&1 | grep -E "Re-replication|dead|Successfully"
```

### Ver logs de uploads

```bash
docker service logs tagfs_gateway 2>&1 | grep -E "Uploading|Upload complete|quorum"
```

### Ver logs de DataNodes

```bash
docker service logs tagfs_data-node 2>&1 | grep -E "Stored|Retrieved"
```

### Monitoreo en tiempo real

```bash
# Terminal 1: Metadata
docker service logs tagfs_metadata --follow

# Terminal 2: Gateway
docker service logs tagfs_gateway --follow

# Terminal 3: DataNodes
docker service logs tagfs_data-node --follow
```

---

## 🧹 Limpieza

### Después de los tests

```bash
# Eliminar archivos temporales (automático en los tests)
rm -f /tmp/test_*.* /tmp/downloaded_*.*

# Detener stack (opcional)
docker stack rm tagfs

# Esperar a que se detengan los servicios
sleep 10

# Limpiar volúmenes (CUIDADO: elimina todos los datos)
docker volume prune -f
```

---

## 🔐 Tests con TLS

Para ejecutar tests con TLS habilitado:

```bash
# 1. Generar certificados
./generate_certs.sh

# 2. Editar docker-stack-distributed.yml
# Agregar a cada servicio:
#   environment:
#     - ENABLE_TLS=true
#     - CERT_DIR=/app/certs
#   volumes:
#     - ./certs:/app/certs:ro

# 3. Desplegar
docker stack deploy -c docker-stack-distributed.yml tagfs

# 4. Ejecutar tests normalmente
./run_all_tests.sh
```

Los tests funcionarán igual con o sin TLS, pero los logs mostrarán:
```
[Gateway] TLS enabled for gRPC connections
[Metadata] TLS enabled on port 50051
[datanode-xxx] TLS enabled on port 50051
```

---

**Última actualización:** 14 de Diciembre de 2025  
**Versión:** 1.0.0 - Production Ready
