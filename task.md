Plan de Mejoras - TagFS Distribuido (Alineado con Informe SD)
🔴 FASE 1: Fundamentos Distribuidos (Semanas 1-3) - CRÍTICO
Algoritmo de Bully para Elección de Líder
 Crear 
services/metadata/bully.py
 con implementación completa
 Actualizar 
protos/service.proto
 con RPCs de Bully
 Regenerar código gRPC (build-images.sh)
 Integrar Bully en 
services/metadata/main.py
 Añadir handlers para Election, Coordinator, LeaderHeartbeat
 Enforcar escrituras solo en líder (CommitWrite)
 Configurar NODE_ID en docker-stack para cada réplica
 Desplegar 3 réplicas de Metadata con IDs únicos
 Probar elección de líder con 3 nodos
 Probar re-elección tras caída del líder
 Verificar solo líder procesa escrituras
 Crear test_bully.py
Relojes de Lamport
 Crear services/metadata/lamport.py
 Implementar LamportClock class
 Añadir campo lamport_timestamp a FileMetadata
 Modificar CommitWrite para incrementar reloj
 Propagar timestamps a followers
 Verificar ordenación causal de eventos
Vectores de Versión
 Crear services/metadata/vector_clock.py
 Implementar VectorClock class
 Añadir campo vector_clock a FileMetadata
 Implementar detección de conflictos
 Implementar resolución LWW (Last Writer Wins)
 Probar detección de escrituras concurrentes
Quorum W=2 (Tolerancia Nivel 2)
 Cambiar WRITE_QUORUM de 1 a 2 en gateway/main.py
 Implementar rollback si no se alcanza quorum
 Actualizar READ_QUORUM a 2
 Verificar R + W > N (2 + 2 > 3)
 Ejecutar tests con nuevo quorum
 Documentar comportamiento con <2 nodos
🟡 FASE 2: Consistencia Eventual (Semanas 4-5)
Protocolo Gossip
 Crear services/metadata/gossip.py
 Implementar GossipProtocol class
 Configurar fanout=3, interval=5s
 Integrar con Metadata service
 Probar propagación de actualizaciones
 Medir tiempo de convergencia
Árboles de Merkle
 Crear services/metadata/merkle.py
 Implementar MerkleTree class
 Implementar comparación de árboles
 Implementar anti-entropy sync
 Probar reconciliación tras partición
 Medir eficiencia de sincronización
🟢 FASE 3: Persistencia y HA (Semanas 6-7)
Persistencia de Metadata
 Crear services/metadata/database.py con SQLAlchemy
 Implementar FileMetadata model
 Modificar CommitWrite para usar DB
 Modificar LocateFile para leer de DB
 Modificar ListFiles para leer de DB
 Añadir volumen metadata-store en docker-stack
 Ejecutar Test 6 CAP y verificar que pasa
Health Checks
 Añadir endpoint /health en Gateway
 Añadir endpoint /ready en Gateway
 Implementar Ping RPC en todos los servicios
 Probar health checks manualmente
Logging Estructurado
 Crear utils/logger.py con JSONFormatter
 Integrar en todos los servicios
 Añadir contexto (user_id, file_id, duration)
 Verificar logs en formato JSON
🔐 FASE 4: Seguridad (Semana 8)
TLS para gRPC
 Generar certificados SSL
 Configurar TLS en Gateway
 Configurar TLS en Metadata
 Configurar TLS en DataNode
 Verificar comunicación cifrada
Progreso Actual
Completado:

✅ Implementación completa de Bully algorithm
✅ Actualización de protobuf con RPCs de Bully
✅ Regeneración de código gRPC
✅ Integración de Bully en Metadata service
✅ Handlers RPC: Election, Coordinator, LeaderHeartbeat
✅ Enforcement de leader-only writes
Próximo:

⏭️ Configurar docker-stack con 3 réplicas de Metadata
⏭️ Asignar NODE_IDs únicos (1, 2, 3)
⏭️ Probar elección de líder