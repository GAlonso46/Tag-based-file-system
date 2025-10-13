"""
Modelos SQLAlchemy para User y File
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    """Modelo de Usuario"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Integer, default=0)  # 0 = usuario normal, 1 = admin
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación con archivos
    files = relationship("FileDB", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"


class FileDB(Base):
    """
    Modelo de Archivo en BD
    Almacena metadata de archivos y su relación con usuarios
    """
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)  # Nombre original sin modificar
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tags = Column(Text, default="")  # JSON string de tags: '["tag1", "tag2"]'
    size = Column(Integer, default=0)  # Tamaño en bytes
    mime_type = Column(String(100), nullable=True)  # Tipo MIME del archivo
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con usuario
    owner = relationship("User", back_populates="files")
    
    def __repr__(self):
        return f"<FileDB {self.filename} (owner: {self.owner_id})>"
