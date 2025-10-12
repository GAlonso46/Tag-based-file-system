import os
from typing import Iterable, List, Tuple
from tags.data.file_store import FileStore
from tags.utils.helpers import normalize_tags

class TagService:
    """
    Lógica de negocio de alto nivel: añade ficheros con tags, listados,
    borrado por tags, añadir/quitar tags por consulta, etc.
    """

    def __init__(self, data_dir: str = None):
        self.store = FileStore(data_dir)

    def add_files(self, file_paths: Iterable[str], tags_raw: str | Iterable[str]) -> List[str]:
        tags = normalize_tags(tags_raw)
        added = []
        for path in file_paths:
            path = os.path.normpath(str(path))
            if not os.path.isfile(path):
                # no se añade
                print(path + " not a regular file")
                continue
            name = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
                # prueba
                print(data)
            self.store.add_file(name, data)
            if tags:
                self.store.add_tags(name, tags)
            added.append(name)
        return added

    def delete_by_tags(self, tags_raw: str | Iterable[str]) -> List[str]:
        tags = normalize_tags(tags_raw)
        matched = self.store.files_matching(tags)
        for m in matched:
            self.store.delete_file(m)
        return matched

    def list_by_tags(self, tags_raw: str | Iterable[str]) -> List[Tuple[str, List[str]]]:
        tags = normalize_tags(tags_raw)
        matched = self.store.files_matching(tags)
        return [(m, list(self.store.meta.get(m, []))) for m in matched]

    def add_tags_to_query(self, query_raw: str | Iterable[str], add_raw: str | Iterable[str]) -> List[str]:
        q = normalize_tags(query_raw)
        to_add = normalize_tags(add_raw)
        matched = self.store.files_matching(q)
        for m in matched:
            self.store.add_tags(m, to_add)
        return matched

    def remove_tags_from_query(self, query_raw: str | Iterable[str], rem_raw: str | Iterable[str]) -> List[str]:
        q = normalize_tags(query_raw)
        rem = normalize_tags(rem_raw)
        matched = self.store.files_matching(q)
        for m in matched:
            self.store.remove_tags(m, rem)
        return matched

    def show_all(self) -> List[Tuple[str, List[str]]]:
        return list(self.store.list_files())
