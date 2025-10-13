"""
Módulo para sincronizar el CLI con la API backend
Permite que los archivos añadidos desde el CLI se registren en la BD
"""
import os
import requests
from typing import Optional

class APISync:
    """Clase para sincronizar operaciones del CLI con la API"""
    
    def __init__(self, api_url: Optional[str] = None):
        """
        Inicializa el sincronizador
        
        Args:
            api_url: URL del backend API (default: http://backend:8000)
        """
        self.api_url = api_url or os.getenv("API_URL", "http://localhost:8000")
        self.enabled = True
        
        # Verificar si el backend está disponible
        try:
            response = requests.get(f"{self.api_url}/", timeout=2)
            if response.status_code != 200:
                print(f"⚠️  Backend API no disponible en {self.api_url}")
                self.enabled = False
        except Exception as e:
            print(f"⚠️  No se pudo conectar al backend: {e}")
            print("   El CLI funcionará en modo local (sin sincronización con BD)")
            self.enabled = False
    
    def sync_to_database(self) -> bool:
        """
        Sincroniza files.json con la base de datos
        Los archivos se asignan automáticamente al usuario admin
        
        Returns:
            True si la sincronización fue exitosa, False en caso contrario
        """
        if not self.enabled:
            return False
        
        try:
            response = requests.post(
                f"{self.api_url}/cli/sync",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("synced", 0) > 0:
                    print(f"✅ Sincronizado: {data['synced']} archivo(s) → admin ({data['admin_user']})")
                return True
            else:
                print(f"⚠️  Error en sincronización: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️  Error al sincronizar con la BD: {e}")
            return False
    
    def get_cli_files(self, tags: Optional[str] = None):
        """
        Obtiene la lista de archivos desde el endpoint CLI
        
        Args:
            tags: Tags para filtrar (opcional)
        
        Returns:
            Lista de archivos o None si hay error
        """
        if not self.enabled:
            return None
        
        try:
            params = {"tags": tags} if tags else {}
            response = requests.get(
                f"{self.api_url}/cli/files",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            print(f"⚠️  Error al obtener archivos: {e}")
            return None
    
    def get_cli_tags(self):
        """
        Obtiene todos los tags desde el endpoint CLI
        
        Returns:
            Lista de tags o None si hay error
        """
        if not self.enabled:
            return None
        
        try:
            response = requests.get(
                f"{self.api_url}/cli/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json().get("tags", [])
            else:
                return None
                
        except Exception as e:
            print(f"⚠️  Error al obtener tags: {e}")
            return None
