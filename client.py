
from typing import Dict

from server import DataCenter
from dfs import DistributedFileSystem


class CacheEntry:
    """
    Single cached file on a client device.
    """
    def __init__(self, content: str, version: int):
        self.content = content
        self.version = version
        self.valid = True


class Client:
    """
    Simulated client device with a local cache.
    """
    def __init__(self, name: str, dfs: DistributedFileSystem, preferred_dc: DataCenter):
        self.name = name
        self.dfs = dfs
        self.preferred_dc = preferred_dc
        self.cache: Dict[str, CacheEntry] = {}

    # ---------- Called by server (via callback) ----------

    def invalidate_cache_entry(self, file_name: str):
        """
        Callback used by servers for push-based invalidation.
        """
        entry = self.cache.get(file_name)
        if entry:
            entry.valid = False
            print(f"[CLIENT {self.name}] Cache invalidated for {file_name}")

    # ---------- Client operations ----------

    def read_file(self, file_name: str) -> str:
        """
        Read a file using local cache if up-to-date and valid,
        otherwise refresh from the distributed file system.
        """
        primary = self.dfs.get_primary_server(file_name)
        primary_version = primary.read_file(file_name)
        primary_version_number = primary_version.version if primary_version else 0

        entry = self.cache.get(file_name)
        if entry and entry.valid and entry.version == primary_version_number:
            print(f"[CLIENT {self.name}] Reading {file_name} from CACHE (v{entry.version})")
            return entry.content

        # Need to refresh from nearest replica
        replica_file = self.dfs.read_file(file_name, self.preferred_dc)
        if not replica_file:
            raise RuntimeError(f"[CLIENT {self.name}] Cannot read {file_name} from any server")

        # Update local cache
        self.cache[file_name] = CacheEntry(replica_file.content, replica_file.version)
        # Register for invalidations at the primary
        primary.register_cache_listener(file_name, self.invalidate_cache_entry)

        print(f"[CLIENT {self.name}] Reading {file_name} from SERVER (v{replica_file.version})")
        return replica_file.content

    def write_file(self, file_name: str, new_content: str):
        """
        Write a file:
        - DFS enforces quorum and primary-based replication.
        - On success, client updates its own cache to the new version.
        """
        print(f"[CLIENT {self.name}] Requesting write for {file_name!r}")
        success = self.dfs.write_file_with_quorum(file_name, new_content)
        if not success:
            print(f"[CLIENT {self.name}] Write FAILED for {file_name!r}")
            return

        # Refresh version from primary for cache update
        primary = self.dfs.get_primary_server(file_name)
        fv = primary.read_file(file_name)
        if not fv:
            print(f"[CLIENT {self.name}] Warning: primary missing file after write")
            return

        self.cache[file_name] = CacheEntry(fv.content, fv.version)
        print(f"[CLIENT {self.name}] Write OK, local cache updated {file_name} -> v{fv.version}")
