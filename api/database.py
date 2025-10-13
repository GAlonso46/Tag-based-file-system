"""
Configuración de la base de datos SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Base de datos SQLite (archivo local)
SQLALCHEMY_DATABASE_URL = "sqlite:///./tags_data/users.db"

# Crear engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Solo para SQLite
)

# SessionLocal: cada instancia será una sesión de BD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

# Dependency para obtener sesión de BD
def get_db():
    """
    Genera una sesión de base de datos y la cierra al terminar
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
