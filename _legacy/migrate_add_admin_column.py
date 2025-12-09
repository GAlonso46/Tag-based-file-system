"""
Script para agregar la columna is_admin a la tabla users existente
"""
import sqlite3
import os

DB_PATH = "tags_data/users.db"

def migrate_add_is_admin():
    """Agrega la columna is_admin a la tabla users"""
    
    if not os.path.exists(DB_PATH):
        print("❌ No se encontró la base de datos. Ejecuta el servidor primero.")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar si la columna ya existe
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_admin' in columns:
            print("✅ La columna 'is_admin' ya existe")
        else:
            # Agregar la columna is_admin con valor por defecto 0
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            conn.commit()
            print("✅ Columna 'is_admin' agregada exitosamente")
        
        # Hacer admin al usuario test@gmail.com si existe
        cursor.execute("SELECT id, username, email FROM users WHERE email = ?", ("test@gmail.com",))
        admin_user = cursor.fetchone()
        
        if admin_user:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE email = ?", ("test@gmail.com",))
            conn.commit()
            print(f"✅ Usuario '{admin_user[1]}' ({admin_user[2]}) es ahora ADMIN")
        else:
            print("⚠️ Usuario test@gmail.com no encontrado. Regístralo primero en la aplicación.")
        
        # Mostrar todos los usuarios
        cursor.execute("SELECT id, username, email, is_admin FROM users")
        users = cursor.fetchall()
        
        if users:
            print("\n📋 Usuarios en la base de datos:")
            for user in users:
                role = "ADMIN" if user[3] == 1 else "Usuario"
                print(f"   - ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Rol: {role}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Error SQL: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔄 Migrando base de datos...\n")
    migrate_add_is_admin()
    print("\n✅ Migración completada")
