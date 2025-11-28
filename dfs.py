
from typing import Dict, List, Optional

from server import Server, DataCenter


class DistributedFileSystem:
    """
    Orchestrates 3 data centers with primary-based replication and quorum.
    """
    def __init__(self, servers: List[Server], primary_table: Dict[str, DataCenter]):
        # Map DataCenter -> Server object
        self.servers_by_dc: Dict[DataCenter, Server] = {s.dc: s for s in servers}
        # Map file_name -> DataCenter that is primary
        self.primary_table = primary_table

    # ---------- Helper methods ----------

    def get_primary_server(self, file_name: str) -> Server:
        primary_dc = self.primary_table[file_name]
        return self.servers_by_dc[primary_dc]

    def get_all_servers(self) -> List[Server]:
        return list(self.servers_by_dc.values())

    def get_best_server_for_read(self, preferred_dc: DataCenter) -> Optional[Server]:
        """
        Return the closest (preferred) server if available,
        otherwise fall back to any available server.
        """
        preferred = self.servers_by_dc.get(preferred_dc)
        if preferred and preferred.is_available():
            return preferred

        for s in self.get_all_servers():
            if s.is_available():
                return s
        return None

    # ---------- Operations used by clients ----------

    def read_file(self, file_name: str, preferred_dc: DataCenter):
        """
        Read from nearest available replica. No quorum needed for read in this design (R = 1).
        """
        server = self.get_best_server_for_read(preferred_dc)
        if not server:
            raise RuntimeError("No replica available to serve read")
        return server.read_file(file_name)

    def write_file_with_quorum(self, file_name: str, new_content: str) -> bool:
        """
        Primary-based write with quorum:
        - Ensure at least 2/3 servers are UP before committing.
        - Update primary, then push to the other replicas (push-based replication).
        - Primary also takes care of pushing cache invalidations.
        """
        primary = self.get_primary_server(file_name)
        available_servers = [s for s in self.get_all_servers() if s.is_available()]
        quorum_size = len(available_servers)

        print(f"[DFS] Checking write quorum for {file_name}: {quorum_size}/3 available")

        if quorum_size < 2:
            print(f"[DFS] Write aborted: quorum not satisfied for {file_name}")
            return False

        # Determine new version based on primary's current version
        current = primary.read_file(file_name)
        current_version = current.version if current else 0
        new_version = current_version + 1

        # 1. Update primary
        primary.apply_update(file_name, new_content, new_version)

        # 2. Push update to all other replicas
        for replica in self.get_all_servers():
            if replica is not primary and replica.is_available():
                replica.apply_update(file_name, new_content, new_version)

        # 3. Push-based cache invalidation from primary
        primary.invalidate_caches(file_name)

        print(f"[DFS] Write committed for {file_name} at version {new_version}")
        return True
