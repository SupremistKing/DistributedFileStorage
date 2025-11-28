
"""
Simple simulation driver for the distributed file storage system.

Run with:
    python main.py
"""

from server import Server, DataCenter
from dfs import DistributedFileSystem
from client import Client


def build_system() -> DistributedFileSystem:
    # Create three data center servers
    ny = Server(DataCenter.NEW_YORK)
    to = Server(DataCenter.TORONTO)
    ld = Server(DataCenter.LONDON)

    # Initial files present at all replicas (version 1)
    for s in (ny, to, ld):
        s.store_initial_file("file1.txt", "Initial content of file1", version=1)
        s.store_initial_file("file2.txt", "Initial content of file2", version=1)
        s.store_initial_file("file3.txt", "Initial content of file3", version=1)

    servers = [ny, to, ld]

    # Primary mapping (per assignment)
    primary_table = {
        "file1.txt": DataCenter.NEW_YORK,
        "file2.txt": DataCenter.TORONTO,
        "file3.txt": DataCenter.LONDON,
    }

    dfs = DistributedFileSystem(servers, primary_table)
    return dfs


def main():
    dfs = build_system()

    # Create two clients in different regions
    alice = Client("Alice", dfs, preferred_dc=DataCenter.NEW_YORK)
    bob = Client("Bob", dfs, preferred_dc=DataCenter.LONDON)

    print("\n=== Initial reads (warm up caches) ===")
    alice.read_file("file1.txt")
    bob.read_file("file1.txt")

    print("\n=== Alice updates file1.txt ===")
    alice.write_file("file1.txt", "Updated by Alice at New York")

    print("\n=== Bob reads after Alice's update (should see new version) ===")
    bob.read_file("file1.txt")

    print("\n=== Simulate London server going DOWN and a new write ===")
    london_server = dfs.servers_by_dc[DataCenter.LONDON]
    london_server.bring_down()

    alice.write_file("file1.txt", "Second update while London is down")

    print("\n=== Bob reads again (served from another replica) ===")
    bob.read_file("file1.txt")

    print("\n=== Bring London back and read from Bob again ===")
    london_server.bring_up()
    bob.read_file("file1.txt")


if __name__ == "__main__":
    main()
