#!/usr/bin/env python3
"""
Migración: Agregar columna 'version' a tabla files

Agrega optimistic locking a la tabla de archivos para prevenir
conflictos de edición concurrente entre múltiples frontends/usuarios.

Uso:
    python3 migrate_add_version.py
"""

import os
from sqlalchemy import create_engine, text, Column, Integer
from sqlalchemy.orm import sessionmaker

# Usar la misma DATABASE_URL que la app
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tags_data/users.db")

def migrate():
    """Agregar columna version a tabla files"""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Verificar si la columna ya existe
        if DATABASE_URL.startswith("sqlite"):
            result = conn.execute(text("PRAGMA table_info(files)"))
            columns = [row[1] for row in result]
        else:  # PostgreSQL
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='files'
            """))
            columns = [row[0] for row in result]
        
        if 'version' in columns:
            print("✓ Columna 'version' ya existe en tabla 'files'")
            return
        
        print("Agregando columna 'version' a tabla 'files'...")
        
        try:
            # Agregar columna version con valor default 1
            if DATABASE_URL.startswith("sqlite"):
                # SQLite requiere default en ADD COLUMN
                conn.execute(text(
                    "ALTER TABLE files ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
                ))
            else:  # PostgreSQL
                conn.execute(text(
                    "ALTER TABLE files ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
                ))
            
            conn.commit()
            print("✓ Columna 'version' agregada exitosamente")
            
            # Contar registros afectados
            result = conn.execute(text("SELECT COUNT(*) FROM files"))
            count = result.scalar()
            print(f"✓ {count} registros inicializados con version=1")
            
        except Exception as e:
            print(f"✗ Error durante migración: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    print("=" * 60)
    print("  MIGRACIÓN: Agregar columna 'version' para optimistic locking")
    print("=" * 60)
    print(f"Database: {DATABASE_URL}")
    print()
    
    migrate()
    
    print()
    print("=" * 60)
    print("  Migración completada")
    print("=" * 60)
