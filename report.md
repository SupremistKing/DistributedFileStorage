
# Distributed File Storage System – Design Report

## 1. Replica Management Strategy

### Topology and primaries
The system simulates three data center servers:

- New York
- Toronto
- London

Every server maintains a full replica of all files. Primary-based replication is used:

- `file1.txt` → primary = New York
- `file2.txt` → primary = Toronto
- `file3.txt` → primary = London

This mapping is encoded in the `DistributedFileSystem.primary_table` (see `dfs.py`). Each `Server` instance stores local file replicas as `FileVersion` objects containing `name`, `content`, and a monotonic `version` number.

### Availability and fault tolerance
Each `Server` has an `alive` flag (see `Server.is_available`). When a server goes down, its replicas are temporarily unavailable, but other replicas continue to serve reads and participate in quorum for writes. Because each file is stored on all three data centers, the system can tolerate the loss of any single server without losing data availability.

The helper method `DistributedFileSystem.get_best_server_for_read` selects the preferred (closest) data center if it is available; otherwise it falls back to any other available replica. This models geo-distributed read access while still maintaining resilience to data center failures.

## 2. Quorum Enforcement and Primary-Based Writes

### Quorum parameters
The system uses a simple (N, R, W) quorum model:

- N = 3 replicas (New York, Toronto, London)
- R = 1 for reads (read from the nearest available replica)
- W = 2 for writes (must have at least 2/3 servers available)

`DistributedFileSystem.write_file_with_quorum` counts how many servers are currently available. If fewer than 2 replicas are up, the write is aborted and the client is notified. This satisfies the standard quorum condition:

- R + W > N → 1 + 2 > 3

ensuring that any successful write intersects with any subsequent read and that no stale value is returned when a quorum is reachable.

### Primary-based write path
Even though the quorum check counts all available servers, the actual write is primary-based:

1. **Quorum check** – The DFS verifies that at least 2 servers are available.
2. **Version assignment** – The primary’s current file version is read and incremented to obtain `new_version`.
3. **Primary update** – The primary `Server` applies the update (`Server.apply_update`), storing the new `content` and `version`.
4. **Replica propagation (push-based)** – The DFS calls `apply_update` on the other available replicas so they all converge on the same `version` and `content`.

Because all writes are serialized through the primary and tagged with strictly increasing version numbers, the system avoids conflicting concurrent updates in this simulation. Any failed write (due to insufficient quorum) is not applied on any replica, so replicas never diverge into inconsistent versions.

## 3. Client-Side Caching and Invalidation

### Client cache model
Each client (`client.py`) maintains a simple in-memory cache:

- Key: file name (e.g., `file1.txt`)
- Value: `CacheEntry(content, version, valid)`

When reading a file, the client performs the following steps:

1. Ask the primary server for the current version of the file.
2. If the client has a cache entry with the same `version` and the entry is still marked `valid`, it uses the cached content.
3. Otherwise, it fetches the latest file from the nearest available replica via `DistributedFileSystem.read_file`, stores it in the cache, and registers for invalidation at the primary server.

This ensures that cached data is never used if it is known to be older than the primary’s authoritative version.

### Push-based invalidation
Push-based consistency is implemented by having servers track *cache listeners*:

- The `Server` class maintains `_cache_listeners[file_name]`, a list of callbacks.
- When a client caches a file, it registers its `invalidate_cache_entry` method as a listener with the primary via `Server.register_cache_listener`.
- After a successful write, `DistributedFileSystem.write_file_with_quorum` updates the primary and replicas, then calls `primary.invalidate_caches(file_name)`.
- The primary iterates over all registered callbacks and invokes them, which marks each client’s cache entry as invalid.

Subsequent reads from those clients detect that their cached entries are invalid and re-fetch the latest version from a replica, thereby restoring cache consistency automatically.

### Write behavior and cache updates
When a client successfully writes to a file:

1. The DFS enforces quorum and commits the update on the primary and replicas.
2. The client then reads back the file’s metadata from the primary to discover the new `version` number.
3. The client overwrites its local cache entry with the new content and version.

Other clients that had cached that file receive invalidation callbacks and, on their next read, refresh from the latest version.

## 4. Summary

The implemented system captures the key aspects of a real-world distributed file service:

- **Replica management** – Three fully replicated data centers with primary-based ownership per file.
- **Quorum-based writes** – Writes require a majority of servers to be available (W = 2), ensuring replica consistency even in the presence of failures.
- **Primary-based replication** – All writes flow through a single primary per file, simplifying versioning and ordering of updates.
- **Client-side caching with invalidation** – Clients cache frequently accessed files locally, while push-based invalidation and version checks keep caches consistent with the primary.
- **Push-based consistency protocol** – After each update, the primary pushes changes to replicas and invalidates all known cached copies, guaranteeing that subsequent reads observe the latest committed version when quorum is available.

This design demonstrates how services similar to Dropbox or Google Drive can combine replication, quorum, and client-side caching to deliver high availability and strong consistency guarantees across geographically distributed data centers.
