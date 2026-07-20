# Hiring Radar — Storage & Persistence Layer Architecture

This document describes the design, implementation, and integrity guarantees of the Hiring Radar storage layer.

---

## 1. Storage Architecture

To decouple business logic and high-level repositories from file format details, OS-specific operations, and serialization protocols, we introduced a dedicated `app/storage/` package.

```
       [ Service Layer ]
               │
               ▼
      [ Repository Layer ] (translates entities to/from Pydantic models)
               │
               ▼
        [ JsonStorage ] (orchestrates reads and atomic writes)
               │
         ┌─────┴───────────────┐
         ▼                     ▼
   [ Serializer ]       [ Atomic Layer ]
 (handles encoding/   (manages temp files,
   model parsing)       flushing, fsync)
         │                     │
         └───────────┬─────────┘
                     ▼
              [ Filesystem ]
```

1. **Filesystem (`filesystem.py`)**: Executes low-level directory creation and file reading/writing.
2. **Atomic Write (`atomic.py`)**: Intercepts writes to perform safe writes using temporary files.
3. **Serializer (`serializer.py`)**: Implements `orjson` serialization and deserialization, converting models, lists, and dicts of Pydantic models to JSON bytes and vice-versa.
4. **JsonStorage (`json_storage.py`)**: Coordinates the filesystem, serialization, and atomic writes to provide a unified persistence contract (`read`, `write`, `exists`, `delete`).

---

## 2. Atomic Write Flow

Writing directly to a file is unsafe: if a process crashes, power is lost, or execution is terminated mid-write, the destination file is left partially written and corrupted.

Hiring Radar prevents this by implementing an atomic replacement sequence:

```
[ Data Payload ]
       │
       ▼
 1. Create temporary file (.tmp_*.json) in destination directory
       │
       ▼
 2. Write raw bytes to temporary file
       │
       ▼
 3. Flush file stream buffers
       │
       ▼
 4. Execute fsync() on file descriptor (forces OS write buffers to disk)
       │
       ▼
 5. Close file descriptor
       │
       ▼
 6. (Optional) Create .backup of original destination file if it exists
       │
       ▼
 7. Atomically replace original destination file using os.replace()
```

*Note: The temporary file is created in the **same parent directory** as the destination file. This guarantees they reside on the same drive and mount partition, enabling the operating system to execute a fast, atomic metadata-only renaming replacement.*

---

## 3. Why This Exists

1. **Corruption Prevention**: Atomic writes ensure that even during sudden power losses, incomplete downloads, or process terminations, Hiring Radar never leaves the job database in a corrupted state.
2. **Backend Independence**: Repositories no longer import `orjson`, parse files, or write directly to paths. They only interact with `storage.read()` and `storage.write()`.
3. **SQLite Migration Path**: In the future, the JSON-based storage layer can be swapped with a relational storage engine (such as SQLite) by introducing an `SqliteStorage` backend implementing the same interface. Because repositories and services are decoupled from the physical file layer, this migration can be accomplished without touching any business or presentation code.
