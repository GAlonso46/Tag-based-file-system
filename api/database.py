"""
Configuración de la base de datos SQLAlchemy.

Soporta PostgreSQL (producción) y SQLite (desarrollo) con:
- Retry logic para conexiones
- Pool de conexiones robusto
- Health checks automáticos
"""
import os
import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool

# Leer la URL de la base de datos desde la variable de entorno.
# Si no existe, usar SQLite local como fallback (desarrollo).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tags_data/users.db")

# Crear engine con opciones según el motor
if DATABASE_URL.startswith("sqlite"):
    # SQLite necesita check_same_thread=False
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL: configuración robusta para entorno distribuido
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,          # Verifica conexiones antes de usar
        pool_size=10,                # Pool de 10 conexiones
        max_overflow=20,             # Hasta 30 conexiones totales
        pool_recycle=3600,           # Reciclar conexiones cada hora
        pool_timeout=30,             # Timeout de 30s para obtener conexión
        connect_args={
            "connect_timeout": 10,   # Timeout de conexión inicial
            "options": "-c statement_timeout=30000"  # 30s timeout para queries
        }
    )

# Event listener para reconexión automática
@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log cuando se establece nueva conexión"""
    connection_record.info['pid'] = os.getpid()

@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Verifica que la conexión siga siendo válida"""
    pid = os.getpid()
    if connection_record.info.get('pid') != pid:
        # Conexión de otro proceso, forzar reconexión
        connection_record.dbapi_connection = connection_proxy.dbapi_connection = None
        raise Exception("Connection record belongs to different process")

# SessionLocal: cada instancia será una sesión de BD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

# Dependency para obtener sesión de BD con retry logic
def get_db():
    """
    Genera una sesión de base de datos con retry logic.
    Cierra la sesión automáticamente al terminar.
    """
    max_retries = 3
    retry_delay = 1  # segundos
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            try:
                # Verificar que la conexión funciona
                db.execute(text("SELECT 1"))
                yield db
                break
            except Exception as e:
                db.close()
                if attempt < max_retries - 1:
                    print(f"Error de BD (intento {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise
            finally:
                db.close()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                raise Exception(f"No se pudo conectar a la BD después de {max_retries} intentos: {e}")
