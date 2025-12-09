"""
Script para migrar archivos existentes al usuario admin
y hacer admin al usuario test@gmail.com
"""
import json
import os
from sqlalchemy.orm import Session
from api.database import engine, SessionLocal, Base
from api.models import User, FileDB
from datetime import datetime

def migrate_to_admin():
    """Migra archivos existentes y crea/actualiza usuario admin"""
    
    # Crear sesión de BD
    db = SessionLocal()
    
    try:
        # 1. Buscar o crear usuario admin
        admin_user = db.query(User).filter(User.email == "test@gmail.com").first()
        
        if not admin_user:
            print("❌ Usuario test@gmail.com no encontrado. Por favor regístralo primero.")
            return
        
        # 2. Hacer admin al usuario
        admin_user.is_admin = 1
        db.commit()
        print(f"✅ Usuario '{admin_user.username}' es ahora ADMIN")
        
        # 3. Leer archivos existentes de files.json
        try:
            with open("tags_data/files/files.json", "r", encoding="utf-8") as f:
                files_data = json.load(f)
        except FileNotFoundError:
            print("⚠️  No se encontró files.json, no hay archivos para migrar")
            return
        
        # 4. Verificar si ya existen archivos en la BD
        existing_files_count = db.query(FileDB).count()
        if existing_files_count > 0:
            print(f"⚠️  Ya existen {existing_files_count} archivos en la BD")
            response = input("¿Deseas asociar archivos huérfanos al admin? (s/n): ")
            if response.lower() == 's':
                orphan_files = db.query(FileDB).filter(FileDB.owner_id == None).all()
                for file in orphan_files:
                    file.owner_id = admin_user.id
                db.commit()
                print(f"✅ {len(orphan_files)} archivos asociados al admin")
            return
        
        # 5. Migrar archivos de files.json a la BD
        # Formato: {"filename.txt": ["tag1", "tag2"]}
        migrated_count = 0
        files_dir = "tags_data/files"
        
        for filename, tags_list in files_data.items():
            # Verificar si el archivo ya existe en BD
            existing = db.query(FileDB).filter(
                FileDB.filename == filename
            ).first()
            
            if existing:
                print(f"⏭️  Archivo '{filename}' ya existe, saltando...")
                continue
            
            # Obtener tamaño del archivo si existe
            file_path = os.path.join(files_dir, filename)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # Detectar tipo MIME básico
            mime_type = "application/octet-stream"
            if filename.endswith('.pdf'):
                mime_type = "application/pdf"
            elif filename.endswith(('.png', '.jpg', '.jpeg')):
                mime_type = f"image/{filename.split('.')[-1]}"
            elif filename.endswith('.webp'):
                mime_type = "image/webp"
            
            # Crear nuevo registro en BD
            new_file = FileDB(
                filename=filename,
                original_filename=filename,
                owner_id=admin_user.id,
                tags=json.dumps(tags_list),
                size=file_size,
                mime_type=mime_type,
                created_at=datetime.utcnow()
            )
            db.add(new_file)
            migrated_count += 1
        
        db.commit()
        print(f"\n✅ Migración completada:")
        print(f"   - {migrated_count} archivos asociados a '{admin_user.username}'")
        print(f"   - Usuario '{admin_user.username}' (ID: {admin_user.id}) es ADMIN")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🔄 Iniciando migración de archivos a usuario admin...\n")
    
    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    migrate_to_admin()
    
    print("\n✅ Proceso completado")
