#!/usr/bin/env python3
"""
Script minimal para crear las tablas en la base de datos apuntada por DATABASE_URL.
Usar esto después de configurar y desplegar el servicio de PostgreSQL.

NOTA: Esta versión solo crea las tablas según los modelos SQLAlchemy; la
importación de datos desde SQLite (si procede) requiere migración adicional.
"""
from api.database import Base, engine


def main():
    print("Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente.")


if __name__ == '__main__':
    main()
