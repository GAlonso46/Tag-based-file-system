import os
import json
from typing import List


class FileStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.files_dir = os.path.join(base_dir, 'files')
        self.meta_path = os.path.join(self.files_dir, 'files.json')
        os.makedirs(self.files_dir, exist_ok=True)
        self._load()

    def _load(self):
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.meta = json.load(f)
        except Exception:
            self.meta = {}

    def _save(self):
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.meta, f, indent=2, ensure_ascii=False)

    def add_file(self, name: str, data: bytes):
        path = os.path.join(self.files_dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        if name not in self.meta:
            self.meta[name] = []
        self._save()

    def delete_file(self, name: str):
        path = os.path.join(self.files_dir, name)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        if name in self.meta:
            del self.meta[name]
        self._save()

    def set_tags(self, name: str, tags: List[str]):
        self.meta[name] = list(dict.fromkeys(tags))
        self._save()

    def add_tags(self, name: str, tags: List[str]):
        current = list(dict.fromkeys(self.meta.get(name, [])))
        for t in tags:
            if t not in current:
                current.append(t)
        self.meta[name] = current
        self._save()

    def remove_tags(self, name: str, tags: List[str]):
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
        return [(name, tags) for name, tags in self.meta.items()]

    def files_matching(self, query_tags: List[str]):
        if not query_tags:
            return []
        res = []
        for name, tags in self.meta.items():
            if set(query_tags).issubset(set(tags)):
                res.append(name)
        return res
