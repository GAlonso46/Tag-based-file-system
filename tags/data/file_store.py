import json
import fcntl
import time
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
        """Carga metadata con retry para NFS compartido"""
        if self.meta_path.exists():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with open(self.meta_path, "r", encoding="utf-8") as fh:
                        # Adquirir lock compartido (lectura)
                        fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
                        try:
                            self._meta = json.load(fh)
                        finally:
                            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    return
                except (json.JSONDecodeError, IOError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))  # Backoff exponencial
                        continue
                    else:
                        print(f"Error cargando metadata después de {max_retries} intentos: {e}")
                        self._meta = {}
        else:
            self._meta = {}

    def _save_meta(self):
        """Guarda metadata con lock exclusivo para evitar race conditions"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Crear archivo temporal
                tmp = self.meta_path.with_suffix(f".tmp.{time.time()}")
                
                with open(tmp, "w", encoding="utf-8") as fh:
                    # Adquirir lock exclusivo (escritura)
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(self._meta, fh, indent=2, ensure_ascii=False)
                        fh.flush()
                        # Forzar sync a disco (importante en NFS)
                        import os
                        os.fsync(fh.fileno())
                    finally:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                
                # Atomic rename (seguro en NFS v4)
                tmp.replace(self.meta_path)
                return
                
            except (IOError, OSError) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    print(f"Error guardando metadata después de {max_retries} intentos: {e}")
                    raise
            finally:
                # Limpiar archivo temporal si quedó
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except:
                        pass

    def reload_meta(self):
        """
        Recarga el archivo files.json desde el disco.
        Útil cuando otro nodo modificó el archivo.
        """
        self._load_meta()
    
    @property
    def meta(self):
        """Devuelve el diccionario meta (filename -> [tags])"""
        return self._meta

    # --- file operations ------------------------------------------------
    def add_file(self, name: str, data: bytes):
        """
        Añade/overwrites un archivo físico en files/.
        Usa escritura atómica para evitar corrupción en NFS.
        """
        target = self.files_dir / name
        tmp = target.with_suffix(f".tmp.{time.time()}")
        
        try:
            # Escribir a archivo temporal
            with open(tmp, "wb") as fh:
                fh.write(data)
                # Forzar sync a disco
                import os
                os.fsync(fh.fileno())
            
            # Atomic rename
            tmp.replace(target)
            
            # Actualizar metadata
            if name not in self._meta:
                self._meta[name] = []
                self._save_meta()
                
        except Exception as e:
            # Cleanup en caso de error
            if tmp.exists():
                try:
                    tmp.unlink()
                except:
                    pass
            raise e

    def delete_file(self, name: str):
        """
        Elimina archivo y su metadata si existe.
        Maneja errores de NFS gracefully.
        """
        target = self.files_dir / name
        
        # Intentar eliminar archivo físico
        if target.exists():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    target.unlink()
                    break
                except (IOError, OSError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        print(f"Error eliminando archivo {name}: {e}")
        
        # Actualizar metadata
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
