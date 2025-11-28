
from enum import Enum
from typing import Dict, Callable, List, Optional


class DataCenter(Enum):
    NEW_YORK = "New York"
    TORONTO = "Toronto"
    LONDON = "London"


class FileVersion:
    """
    Represents a single version of a file on a server replica.
    """
    def __init__(self, name: str, content: str, version: int = 0):
        self.name = name
        self.content = content
        self.version = version

    def __repr__(self) -> str:
        return f"FileVersion(name={self.name}, version={self.version})"


class Server:
    """
    Simulated data center server that stores file replicas.
    It also keeps track of cache listeners so it can push invalidations.
    """
    def __init__(self, dc: DataCenter):
        self.dc = dc
        self.files: Dict[str, FileVersion] = {}
        self.alive: bool = True
        # file_name -> list of callbacks (one per client cache)
        self._cache_listeners: Dict[str, List[Callable[[str], None]]] = {}

    def is_available(self) -> bool:
        return self.alive

    def bring_down(self):
        print(f"[SERVER] {self.dc.value}: going DOWN")
        self.alive = False

    def bring_up(self):
        print(f"[SERVER] {self.dc.value}: coming UP")
        self.alive = True

    def store_initial_file(self, name: str, content: str, version: int = 1):
        self.files[name] = FileVersion(name, content, version)
        print(f"[SERVER] {self.dc.value}: stored initial {name} v{version}")

    def read_file(self, name: str) -> Optional[FileVersion]:
        if not self.is_available():
            print(f"[SERVER] {self.dc.value}: read failed for {name} (DOWN)")
            return None
        fv = self.files.get(name)
        print(f"[SERVER] {self.dc.value}: read {fv}")
        return fv

    def apply_update(self, name: str, new_content: str, new_version: int):
        if not self.is_available():
            print(f"[SERVER] {self.dc.value}: cannot apply update (DOWN)")
            return
        if name in self.files:
            self.files[name].content = new_content
            self.files[name].version = new_version
        else:
            self.files[name] = FileVersion(name, new_content, new_version)
        print(f"[SERVER] {self.dc.value}: applied update {name} -> v{new_version}")

    # ---------- Caching registration & invalidation ----------

    def register_cache_listener(self, file_name: str, callback: Callable[[str], None]):
        """
        Clients call this to subscribe their cache to invalidations for file_name.
        """
        listeners = self._cache_listeners.setdefault(file_name, [])
        if callback not in listeners:
            listeners.append(callback)
            print(f"[SERVER] {self.dc.value}: registered cache listener for {file_name}")

    def invalidate_caches(self, file_name: str):
        """
        Push-based invalidation: notify all subscribers that their cache is stale.
        """
        listeners = self._cache_listeners.get(file_name, [])
        print(f"[SERVER] {self.dc.value}: invalidating {len(listeners)} client caches for {file_name}")
        for cb in listeners:
            cb(file_name)
