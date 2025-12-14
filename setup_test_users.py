#!/usr/bin/env python3
"""
Script para limpiar la base de datos y crear usuarios de prueba
"""
import os
import sys
from pathlib import Path

# Add the parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.database import SessionLocal, engine, Base
from api.models import User, FileDB
from api.auth import get_password_hash

def reset_database():
    """Drop all tables and recreate"""
    print("🗑️  Limpiando base de datos...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos limpia")

def create_test_users():
    """Create test users: 1 admin and 2 regular users"""
    db = SessionLocal()
    
    try:
        # Admin user
        admin = User(
            username="admin",
            email="admin@tagfs.com",
            hashed_password=get_password_hash("123456"),
            is_admin=1
        )
        db.add(admin)
        print("✅ Usuario admin creado (username: admin, password: 123456)")
        
        # Regular users
        user1 = User(
            username="alice",
            email="alice@tagfs.com",
            hashed_password=get_password_hash("alice123"),
            is_admin=0
        )
        db.add(user1)
        print("✅ Usuario alice creado (username: alice, password: alice123)")
        
        user2 = User(
            username="bob",
            email="bob@tagfs.com",
            hashed_password=get_password_hash("bob123"),
            is_admin=0
        )
        db.add(user2)
        print("✅ Usuario bob creado (username: bob, password: bob123)")
        
        db.commit()
        
        # Get IDs
        admin_id = admin.id
        alice_id = user1.id
        bob_id = user2.id
        
        print("\n📊 Usuarios creados:")
        print(f"   Admin (ID: {admin_id}): username=admin, password=123456, is_admin=1")
        print(f"   Alice (ID: {alice_id}): username=alice, password=alice123, is_admin=0")
        print(f"   Bob   (ID: {bob_id}): username=bob, password=bob123, is_admin=0")
        
    except Exception as e:
        print(f"❌ Error creando usuarios: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    print("=" * 60)
    print("SETUP DE USUARIOS DE PRUEBA - TagFS")
    print("=" * 60)
    
    reset_database()
    create_test_users()
    
    print("\n" + "=" * 60)
    print("🎉 Setup completado!")
    print("\nPuedes probar con:")
    print("  curl -X POST http://localhost:8000/login \\")
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"username": "admin", "password": "123456"}\'')
    print("=" * 60)

if __name__ == "__main__":
    main()
