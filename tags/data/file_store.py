import json
from pathlib import Path
from typing import Iterable, List
from tags.config import DATA_DIR, FILES_DIRNAME, META_FILENAME

class FileStore:
    """
    Implementación sencilla de persistencia basada en filesystem:
    - archivos binarios en data_dir/files/<name>
    - metadata en data_dir/meta.json como {"filename": ["tag1","tag2", ...], ...}
    """

    def __init__(self, data_dir: str | Path = None):
        self.data_dir = Path(data_dir) if data_dir else Path(DATA_DIR)
        self.files_dir = self.data_dir / FILES_DIRNAME
        self.meta_path = self.files_dir / META_FILENAME
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._meta = None
        self._load_meta()

    # --- meta management ------------------------------------------------
    def _load_meta(self):
        print(self.data_dir)
        print(self.files_dir)
        print(self.meta_path)
        if self.meta_path.exists():
            print("Archivo .json existe")
            try:
                with open(self.meta_path, "r", encoding="utf-8") as fh:
                    self._meta = json.load(fh)
            except Exception:
                print("Archivo .json existe pero no ha sido posible deserializarlo")
                self._meta = {}
        else:
            print("Archivo .json no existe")
            self._meta = {}

    def _save_meta(self):
        tmp = self.meta_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._meta, fh, indent=2, ensure_ascii=False)
        tmp.replace(self.meta_path)

    @property
    def meta(self):
        """Devuelve el diccionario meta (filename -> [tags])"""
        return self._meta

    # --- file operations ------------------------------------------------
    def add_file(self, name: str, data: bytes):
        """Añade/overwrites un archivo físico en files/."""
        target = self.files_dir / name
        with open(target, "wb") as fh:
            fh.write(data)
        # ensure metadata exists
        if name not in self._meta:
            self._meta[name] = []
            self._save_meta()

    def delete_file(self, name: str):
        """Elimina archivo y su metadata si existe."""
        target = self.files_dir / name
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass
        if name in self._meta:
            del self._meta[name]
            self._save_meta()

    def list_files(self) -> Iterable:
        """Iterador de (filename, [tags])"""
        for name, tags in self._meta.items():
            yield name, list(tags)

    # --- tags metadata --------------------------------------------------
    def add_tags(self, name: str, tags: Iterable[str]):
        """Añade tags a un fichero (sin duplicados)."""
        if name not in self._meta:
            self._meta[name] = []
        cur = list(self._meta[name])
        for t in tags:
            if t not in cur:
                cur.append(t)
        self._meta[name] = cur
        self._save_meta()

    def remove_tags(self, name: str, tags: Iterable[str]):
        """Elimina tags de un fichero si existen."""
        if name not in self._meta:
            return
        cur = [t for t in self._meta[name] if t not in set(tags)]
        self._meta[name] = cur
        self._save_meta()

    def files_matching(self, tags: Iterable[str]) -> List[str]:
        """
        Devuelve lista de nombres de ficheros que contienen TODOS los tags
        pasados (matching AND). Si tags está vacío, devuelve todos.
        """
        tags = list(tags or [])
        if not tags:
            return list(self._meta.keys())
        matched = []
        for name, tlist in self._meta.items():
            if all(t in tlist for t in tags):
                matched.append(name)
        return matched
