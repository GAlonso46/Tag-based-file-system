import os
import json
from typing import List


class FileStore:
    """Clase principal para el almacenamiento y gestión de archivos y sus tags."""
    def __init__(self, base_dir: str):
        """Inicializa el FileStore con la ruta base de almacenamiento."""
        self.base_dir = base_dir
        self.files_dir = os.path.join(base_dir, 'files')
        self.meta_path = os.path.join(self.files_dir, 'files.json')
        os.makedirs(self.files_dir, exist_ok=True)
        self._load()

    def _load(self):
        """Carga la metadata de archivos y tags desde el archivo JSON."""
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.meta = json.load(f)
        except Exception:
            self.meta = {}

    def _save(self):
        """Guarda la metadata actual en el archivo JSON."""
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.meta, f, indent=2, ensure_ascii=False)

    def add_file(self, name: str, data: bytes):
        """Agrega un archivo al sistema y lo inicializa sin tags si es nuevo."""
        path = os.path.join(self.files_dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        if name not in self.meta:
            self.meta[name] = []
        self._save()

    def delete_file(self, name: str):
        """Elimina un archivo y su metadata."""
        path = os.path.join(self.files_dir, name)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        if name in self.meta:
            del self.meta[name]
        self._save()

    def set_tags(self, name: str, tags: List[str]):
        """Establece los tags de un archivo, reemplazando los existentes."""
        self.meta[name] = list(dict.fromkeys(tags))
        self._save()

    def add_tags(self, name: str, tags: List[str]):
        """Agrega tags a un archivo, evitando duplicados."""
        current = list(dict.fromkeys(self.meta.get(name, [])))
        for t in tags:
            if t not in current:
                current.append(t)
        self.meta[name] = current
        self._save()

    def remove_tags(self, name: str, tags: List[str]):
        """Elimina tags de un archivo. Si no quedan tags, elimina el archivo."""
        if name not in self.meta:
            return
        current = [t for t in self.meta[name] if t not in tags]
        if current:
            self.meta[name] = current
        else:
            del self.meta[name]
            # also remove file
            p = os.path.join(self.files_dir, name)
            try:
                os.remove(p)
            except Exception:
                pass
        self._save()

    def list_files(self):
        """Devuelve una lista de tuplas (nombre, tags) de todos los archivos."""
        return [(name, tags) for name, tags in self.meta.items()]

    def files_matching(self, query_tags: List[str]):
        """Devuelve los archivos que contienen todos los tags indicados en query_tags."""
        if not query_tags:
            return []
        res = []
        for name, tags in self.meta.items():
            if set(query_tags).issubset(set(tags)):
                res.append(name)
        return res
