"""
Script para inspeccionar el contenido de la base de datos users.db
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = "tags_data/users.db"

def inspect_database():
    """Muestra el contenido de la base de datos"""
    
    if not Path(DB_PATH).exists():
        print("❌ No se encontró la base de datos")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("📊 INSPECCIÓN DE BASE DE DATOS users.db")
        print("=" * 70)
        
        # Listar todas las tablas
        print("\n📋 TABLAS EN LA BASE DE DATOS:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"   - {table[0]}")
        
        # Estructura de la tabla users
        print("\n" + "=" * 70)
        print("👥 TABLA: users")
        print("=" * 70)
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("\nColumnas:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]}){' - PRIMARY KEY' if col[5] else ''}")
        
        # Mostrar usuarios
        print("\nUsuarios registrados:")
        cursor.execute("SELECT id, username, email, is_admin, created_at FROM users")
        users = cursor.fetchall()
        if users:
            for user in users:
                role = "🔴 ADMIN" if user[3] == 1 else "🔵 Usuario"
                print(f"\n   ID: {user[0]}")
                print(f"   Username: {user[1]}")
                print(f"   Email: {user[2]}")
                print(f"   Rol: {role}")
                print(f"   Creado: {user[4]}")
        else:
            print("   No hay usuarios registrados")
        
        # Estructura de la tabla files
        print("\n" + "=" * 70)
        print("📁 TABLA: files")
        print("=" * 70)
        cursor.execute("PRAGMA table_info(files)")
        columns = cursor.fetchall()
        print("\nColumnas:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]}){' - PRIMARY KEY' if col[5] else ''}")
        
        # Mostrar archivos
        print("\nArchivos registrados:")
        cursor.execute("""
            SELECT f.id, f.filename, f.size, f.mime_type, f.tags, f.owner_id, u.username
            FROM files f
            LEFT JOIN users u ON f.owner_id = u.id
        """)
        files = cursor.fetchall()
        if files:
            for file in files:
                tags_list = json.loads(file[4]) if file[4] else []
                print(f"\n   ID: {file[0]}")
                print(f"   Archivo: {file[1]}")
                print(f"   Tamaño: {file[2]} bytes ({file[2] / 1024:.2f} KB)")
                print(f"   Tipo: {file[3]}")
                print(f"   Tags: {', '.join(tags_list)}")
                print(f"   Propietario: {file[6]} (ID: {file[5]})")
        else:
            print("   No hay archivos registrados")
        
        # Resumen
        print("\n" + "=" * 70)
        print("📈 RESUMEN")
        print("=" * 70)
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        total_admins = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(size) FROM files")
        total_size = cursor.fetchone()[0] or 0
        
        print(f"\n   Total de usuarios: {total_users}")
        print(f"   Administradores: {total_admins}")
        print(f"   Usuarios normales: {total_users - total_admins}")
        print(f"   Total de archivos: {total_files}")
        print(f"   Tamaño total: {total_size} bytes ({total_size / 1024 / 1024:.2f} MB)")
        
        print("\n" + "=" * 70)
        print("✅ Inspección completada")
        print("=" * 70)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Error SQL: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    inspect_database()
