#!/usr/bin/env python3
"""
Script completo de migración de datos desde SQLite a PostgreSQL.

Migra:
1. Usuarios desde users.db (SQLite)
2. Archivos metadata desde users.db
3. Tags desde files.json (si procede)

PREREQUISITOS:
- Tener DATABASE_URL apuntando a PostgreSQL
- Tener los archivos users.db y files.json en tags_data/

USO:
    export DATABASE_URL="postgresql://tagfs_user:password@database:5432/tagfs"
    python migrate_sqlite_to_postgres.py
"""
import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Importar modelos y engine de la aplicación
from api.database import Base, engine, SessionLocal
from api.models import User, FileDB


def migrate_users(sqlite_db_path: str, session):
    """Migra usuarios desde SQLite a PostgreSQL"""
    print(f"\n[1/3] Migrando usuarios desde {sqlite_db_path}...")
    
    if not os.path.exists(sqlite_db_path):
        print(f"⚠️  Advertencia: {sqlite_db_path} no existe, saltando migración de usuarios")
        return 0
    
    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Verificar si la tabla users existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("⚠️  Tabla 'users' no encontrada en SQLite")
            conn.close()
            return 0
        
        # Leer usuarios
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        migrated = 0
        skipped = 0
        
        for user_row in users:
            # Verificar si el usuario ya existe
            existing = session.query(User).filter(User.username == user_row['username']).first()
            if existing:
                print(f"  ⏭️  Usuario '{user_row['username']}' ya existe, saltando")
                skipped += 1
                continue
            
            # Crear nuevo usuario
            new_user = User(
                id=user_row['id'],
                username=user_row['username'],
                email=user_row['email'],
                hashed_password=user_row['hashed_password'],
                is_admin=user_row.get('is_admin', 0),
                created_at=user_row.get('created_at', datetime.utcnow())
            )
            session.add(new_user)
            migrated += 1
            print(f"  ✅ Usuario migrado: {user_row['username']}")
        
        session.commit()
        print(f"\n✅ Migración de usuarios completada: {migrated} migrados, {skipped} saltados")
        
    except Exception as e:
        print(f"❌ Error migrando usuarios: {e}")
        session.rollback()
        raise
    finally:
        conn.close()
    
    return migrated


def migrate_files(sqlite_db_path: str, session):
    """Migra metadata de archivos desde SQLite a PostgreSQL"""
    print(f"\n[2/3] Migrando archivos desde {sqlite_db_path}...")
    
    if not os.path.exists(sqlite_db_path):
        print(f"⚠️  Advertencia: {sqlite_db_path} no existe, saltando migración de archivos")
        return 0
    
    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Verificar si la tabla files existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
        if not cursor.fetchone():
            print("⚠️  Tabla 'files' no encontrada en SQLite")
            conn.close()
            return 0
        
        # Leer archivos
        cursor.execute("SELECT * FROM files")
        files = cursor.fetchall()
        
        migrated = 0
        skipped = 0
        
        for file_row in files:
            # Verificar si el archivo ya existe
            existing = session.query(FileDB).filter(FileDB.filename == file_row['filename']).first()
            if existing:
                print(f"  ⏭️  Archivo '{file_row['filename']}' ya existe, saltando")
                skipped += 1
                continue
            
            # Crear nuevo archivo
            new_file = FileDB(
                id=file_row['id'],
                filename=file_row['filename'],
                original_filename=file_row['original_filename'],
                owner_id=file_row['owner_id'],
                tags=file_row.get('tags', '[]'),
                size=file_row.get('size', 0),
                mime_type=file_row.get('mime_type', 'application/octet-stream'),
                created_at=file_row.get('created_at', datetime.utcnow()),
                updated_at=file_row.get('updated_at', datetime.utcnow())
            )
            session.add(new_file)
            migrated += 1
            print(f"  ✅ Archivo migrado: {file_row['filename']}")
        
        session.commit()
        print(f"\n✅ Migración de archivos completada: {migrated} migrados, {skipped} saltados")
        
    except Exception as e:
        print(f"❌ Error migrando archivos: {e}")
        session.rollback()
        raise
    finally:
        conn.close()
    
    return migrated


def sync_files_json(files_json_path: str, session):
    """
    Sincroniza archivos desde files.json hacia PostgreSQL.
    Solo crea registros para archivos que no estén ya en la BD.
    Asigna archivos huérfanos al primer usuario admin encontrado.
    """
    print(f"\n[3/3] Sincronizando desde {files_json_path}...")
    
    if not os.path.exists(files_json_path):
        print(f"⚠️  Advertencia: {files_json_path} no existe, saltando sincronización")
        return 0
    
    try:
        with open(files_json_path, 'r', encoding='utf-8') as f:
            files_data = json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo {files_json_path}: {e}")
        return 0
    
    # Obtener usuario admin (para asignar archivos huérfanos)
    admin_user = session.query(User).filter(User.is_admin == 1).first()
    if not admin_user:
        print("⚠️  No hay usuarios admin, creando usuario admin por defecto...")
        from api.dependencies import get_password_hash
        admin_user = User(
            username="admin",
            email="admin@tagfs.local",
            hashed_password=get_password_hash("admin123"),
            is_admin=1
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        print(f"  ✅ Usuario admin creado: username='admin', password='admin123'")
    
    migrated = 0
    skipped = 0
    files_dir = Path(files_json_path).parent
    
    for filename, tags in files_data.items():
        # Verificar si ya existe en BD
        existing = session.query(FileDB).filter(FileDB.filename == filename).first()
        if existing:
            skipped += 1
            continue
        
        # Obtener tamaño del archivo
        file_path = files_dir / filename
        size = file_path.stat().st_size if file_path.exists() else 0
        
        # Crear registro
        new_file = FileDB(
            filename=filename,
            original_filename=filename,
            owner_id=admin_user.id,
            tags=json.dumps(tags),
            size=size,
            mime_type="application/octet-stream"
        )
        session.add(new_file)
        migrated += 1
        print(f"  ✅ Sincronizado desde files.json: {filename}")
    
    session.commit()
    print(f"\n✅ Sincronización completada: {migrated} nuevos, {skipped} saltados")
    
    return migrated


def main():
    print("=" * 60)
    print("  Migración SQLite → PostgreSQL")
    print("=" * 60)
    
    # Verificar que DATABASE_URL apunta a PostgreSQL
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        print("❌ Error: DATABASE_URL debe apuntar a PostgreSQL")
        print(f"   Actual: {database_url}")
        print("\nConfigura DATABASE_URL antes de ejecutar:")
        print('  export DATABASE_URL="postgresql://user:pass@host:port/dbname"')
        sys.exit(1)
    
    print(f"\n📊 Base de datos destino: {database_url.split('@')[-1]}")
    
    # Crear tablas si no existen
    print("\n[0/3] Creando tablas si no existen...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas verificadas/creadas")
    
    # Crear sesión
    session = SessionLocal()
    
    try:
        # Rutas de archivos fuente
        sqlite_db = "./tags_data/users.db"
        files_json = "./tags_data/files/files.json"
        
        # Migrar datos
        total_users = migrate_users(sqlite_db, session)
        total_files = migrate_files(sqlite_db, session)
        total_synced = sync_files_json(files_json, session)
        
        print("\n" + "=" * 60)
        print("  📊 RESUMEN DE MIGRACIÓN")
        print("=" * 60)
        print(f"  Usuarios migrados:        {total_users}")
        print(f"  Archivos migrados:        {total_files}")
        print(f"  Archivos sincronizados:   {total_synced}")
        print(f"  Total:                    {total_users + total_files + total_synced}")
        print("=" * 60)
        print("\n✅ Migración completada exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    main()
