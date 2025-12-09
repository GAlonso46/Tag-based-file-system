#!/usr/bin/env python3
"""
Test del backend API sin Docker.

Prueba:
- Importación de módulos
- Creación de la app FastAPI
- Endpoints básicos
- Conexión a BD (SQLite)
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

print("=" * 60)
print("  Test del Backend API")
print("=" * 60)

# Test 1: Importar módulos
print("\n[TEST 1] Importar módulos...")
try:
    from api.main import app
    from api.database import engine, Base, get_db
    from api.models import User, FileDB
    from api.auth import router as auth_router
    print("  ✓ Todos los módulos se importan correctamente")
except ImportError as e:
    print(f"  ✗ Error importando: {e}")
    sys.exit(1)

# Test 2: Verificar que la app FastAPI existe
print("\n[TEST 2] Verificar app FastAPI...")
try:
    assert app is not None, "App no existe"
    assert hasattr(app, 'routes'), "App no tiene routes"
    print(f"  ✓ App FastAPI creada con {len(app.routes)} rutas")
except AssertionError as e:
    print(f"  ✗ {e}")
    sys.exit(1)

# Test 3: Verificar rutas críticas
print("\n[TEST 3] Verificar rutas del API...")
try:
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    
    critical_routes = [
        "/",
        "/auth/register",
        "/auth/login",
        "/files",
        "/tags",
        "/stats"
    ]
    
    for route in critical_routes:
        assert any(r == route or r.startswith(route + "/") for r in routes), f"Ruta {route} no encontrada"
        print(f"  ✓ Ruta {route} existe")
    
except AssertionError as e:
    print(f"  ✗ {e}")
    sys.exit(1)

# Test 4: Crear tablas en BD temporal
print("\n[TEST 4] Crear tablas en BD...")
try:
    # Usar BD temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['DATABASE_URL'] = f"sqlite:///{tmpdir}/test.db"
        
        # Recrear engine con nueva URL
        from sqlalchemy import create_engine
        test_engine = create_engine(
            os.environ['DATABASE_URL'],
            connect_args={"check_same_thread": False}
        )
        
        # Crear tablas
        Base.metadata.create_all(bind=test_engine)
        
        # Verificar que las tablas existen
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        
        assert 'users' in tables, "Tabla users no creada"
        assert 'files' in tables, "Tabla files no creada"
        print(f"  ✓ Tablas creadas: {', '.join(tables)}")
        
        # Verificar columnas de users
        user_columns = [col['name'] for col in inspector.get_columns('users')]
        required_cols = ['id', 'username', 'email', 'hashed_password', 'is_admin']
        
        for col in required_cols:
            assert col in user_columns, f"Columna {col} no existe en users"
        print(f"  ✓ Tabla users tiene todas las columnas necesarias")
        
        # Verificar columnas de files
        file_columns = [col['name'] for col in inspector.get_columns('files')]
        required_cols = ['id', 'filename', 'owner_id', 'tags', 'size', 'mime_type']
        
        for col in required_cols:
            assert col in file_columns, f"Columna {col} no existe en files"
        print(f"  ✓ Tabla files tiene todas las columnas necesarias")

except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Test de dependencias
print("\n[TEST 5] Test de dependencias...")
try:
    from api.dependencies import get_password_hash, verify_password, create_access_token
    
    # Test hash de password
    password = "test123"
    hashed = get_password_hash(password)
    assert hashed != password, "Password no fue hasheado"
    assert verify_password(password, hashed), "Verificación de password falla"
    print("  ✓ Hash y verificación de passwords funciona")
    
    # Test creación de token
    token = create_access_token(data={"sub": "testuser"})
    assert isinstance(token, str), "Token no es string"
    assert len(token) > 20, "Token demasiado corto"
    print("  ✓ Creación de JWT tokens funciona")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Verificar TagService
print("\n[TEST 6] Test de TagService...")
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        from tags.core.tag_service import TagService
        
        service = TagService(tmpdir)
        
        # Test agregar archivo
        test_file = Path(tmpdir) / "files" / "test.txt"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("test content")
        
        service.store.add_tags("test.txt", ["tag1", "tag2"])
        
        # Test buscar
        results = service.list_by_tags("tag1")
        assert len(results) > 0, "Búsqueda por tags falla"
        assert any(name == "test.txt" for name, _ in results), "Archivo no encontrado"
        print("  ✓ TagService funciona correctamente")
        
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Test de CRUD en modelos
print("\n[TEST 7] Test CRUD en modelos...")
try:
    from sqlalchemy.orm import sessionmaker
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup BD temporal
        test_db_url = f"sqlite:///{tmpdir}/test.db"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=test_engine)
        SessionLocal = sessionmaker(bind=test_engine)
        
        session = SessionLocal()
        
        try:
            # Crear usuario
            from api.dependencies import get_password_hash
            
            user = User(
                username="testuser",
                email="test@example.com",
                hashed_password=get_password_hash("test123"),
                is_admin=0
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            
            assert user.id is not None, "User ID no asignado"
            print(f"  ✓ Usuario creado con ID {user.id}")
            
            # Crear archivo
            import json
            
            file_db = FileDB(
                filename="test.pdf",
                original_filename="test.pdf",
                owner_id=user.id,
                tags=json.dumps(["test", "pdf"]),
                size=1024,
                mime_type="application/pdf"
            )
            session.add(file_db)
            session.commit()
            session.refresh(file_db)
            
            assert file_db.id is not None, "File ID no asignado"
            print(f"  ✓ Archivo creado con ID {file_db.id}")
            
            # Verificar relación
            assert file_db.owner.username == "testuser", "Relación owner no funciona"
            assert len(user.files) == 1, "Relación files no funciona"
            print("  ✓ Relaciones User-File funcionan correctamente")
            
        finally:
            session.close()
            
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Resumen final
print("\n" + "=" * 60)
print("  ✅ TODOS LOS TESTS DEL BACKEND PASARON")
print("=" * 60)
print("\n📝 Componentes validados:")
print("  - Importación de módulos")
print("  - App FastAPI con rutas")
print("  - Modelos de BD (Users, Files)")
print("  - Hash de passwords y JWT")
print("  - TagService")
print("  - CRUD operations")
print("\n🚀 El backend está listo para ejecutarse")
print("")

sys.exit(0)
