#!/usr/bin/env python3
"""
Script de optimización para PostgreSQL.

Crea índices adicionales para mejorar performance de queries:
- Índice GIN para búsquedas en tags JSON
- Índice compuesto para owner_id + created_at
- Estadísticas y análisis de tablas

PREREQUISITOS:
- DATABASE_URL configurado apuntando a PostgreSQL
- Tablas ya creadas

USO:
    export DATABASE_URL="postgresql://tagfs_user:password@database:5432/tagfs"
    python optimize_postgres.py
"""
import os
import sys
from sqlalchemy import text, inspect
from api.database import engine, SessionLocal


def optimize_database():
    """Aplica optimizaciones a la base de datos PostgreSQL"""
    print("=" * 60)
    print("  Optimización de PostgreSQL")
    print("=" * 60)
    
    # Verificar que es PostgreSQL
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        print("❌ Este script solo funciona con PostgreSQL")
        print(f"   DATABASE_URL actual: {database_url}")
        sys.exit(1)
    
    print(f"\n📊 Base de datos: {database_url.split('@')[-1]}\n")
    
    session = SessionLocal()
    
    try:
        # 1. Crear índice GIN para búsquedas en tags (JSON)
        print("[1/5] Creando índice GIN para tags...")
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_files_tags_gin 
                ON files USING GIN (to_tsvector('english', tags))
            """))
            session.commit()
            print("  ✅ Índice GIN creado para búsquedas de texto en tags")
        except Exception as e:
            print(f"  ⚠️  Índice GIN ya existe o error: {e}")
            session.rollback()
        
        # 2. Índice compuesto para consultas por propietario
        print("\n[2/5] Creando índice compuesto owner_id + created_at...")
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_files_owner_created 
                ON files (owner_id, created_at DESC)
            """))
            session.commit()
            print("  ✅ Índice compuesto creado para consultas por propietario")
        except Exception as e:
            print(f"  ⚠️  Índice compuesto ya existe o error: {e}")
            session.rollback()
        
        # 3. Índice para búsquedas por mime_type
        print("\n[3/5] Creando índice para mime_type...")
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_files_mime_type 
                ON files (mime_type)
            """))
            session.commit()
            print("  ✅ Índice creado para búsquedas por tipo MIME")
        except Exception as e:
            print(f"  ⚠️  Índice mime_type ya existe o error: {e}")
            session.rollback()
        
        # 4. Actualizar estadísticas de las tablas
        print("\n[4/5] Actualizando estadísticas de las tablas...")
        try:
            session.execute(text("ANALYZE users"))
            session.execute(text("ANALYZE files"))
            session.commit()
            print("  ✅ Estadísticas actualizadas")
        except Exception as e:
            print(f"  ⚠️  Error actualizando estadísticas: {e}")
            session.rollback()
        
        # 5. Mostrar información de índices
        print("\n[5/5] Verificando índices creados...")
        result = session.execute(text("""
            SELECT 
                tablename, 
                indexname, 
                indexdef 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('users', 'files')
            ORDER BY tablename, indexname
        """))
        
        print("\n📋 Índices actuales:")
        for row in result:
            print(f"  - {row.tablename}.{row.indexname}")
        
        # Mostrar estadísticas de tamaño
        print("\n📊 Tamaño de las tablas:")
        result = session.execute(text("""
            SELECT 
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('users', 'files')
        """))
        
        for row in result:
            print(f"  - {row.tablename}: {row.size}")
        
        # Contar registros
        print("\n📈 Registros por tabla:")
        users_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        files_count = session.execute(text("SELECT COUNT(*) FROM files")).scalar()
        print(f"  - users: {users_count}")
        print(f"  - files: {files_count}")
        
        print("\n" + "=" * 60)
        print("✅ Optimización completada exitosamente")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error durante la optimización: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    optimize_database()
