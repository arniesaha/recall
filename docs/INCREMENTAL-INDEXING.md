# Incremental Indexing Design

## Overview

The indexing system supports both full reindex and incremental indexing. Callers use `/index/start`, and the backend determines whether to do a full or incremental index based on the `full` parameter.

## API Contract

```
POST /index/start
{
  "vault": "all" | "work" | "personal",
  "full": false,                    // false = incremental (default)
  "callback_url": "https://..."     // optional webhook
}
```

- `full: true` → Full reindex (clears table, re-indexes everything)
- `full: false` → Incremental (only new/modified/deleted files)

Use `full: false` for regular scheduled syncs.

## Incremental Logic (Backend)

### Change Detection Strategy

**Two-tier change detection:**

1. **Fast tier: mtime check (filesystem stat)**
   - Store `mtime` (file modification timestamp) in the index
   - On incremental run, stat each file and compare mtime
   - If mtime unchanged → skip (no read required)
   - If mtime changed → proceed to content check

2. **Accurate tier: content hash**
   - Only for files where mtime changed
   - Read file, compute MD5 hash
   - Compare against stored `file_hash`
   - If hash unchanged → skip (mtime was misleading, e.g., touch)
   - If hash changed → re-index

### Operations

| Scenario | Detection | Action |
|----------|-----------|--------|
| File unchanged | mtime same | Skip |
| File modified | mtime changed + hash changed | Delete old chunks, re-index |
| File touched (no content change) | mtime changed + hash same | Skip |
| New file | Not in index | Index |
| File deleted | In index but not on disk | Delete from index |

### Deletion Handling

1. Build set of all files currently on disk
2. Query index for all indexed file paths
3. Find files in index but not on disk → delete from index

## Schema

The `DocumentChunk` includes `mtime` for change detection:

```python
class DocumentChunk(LanceModel):
    id: str
    vector: Vector(768)
    file_path: str
    file_hash: str
    mtime: float              # file modification time (Unix timestamp)
    title: str
    # ... rest unchanged
```

## Performance

| Files | Full (read all) | Incremental (mtime check) |
|-------|-----------------|---------------------------|
| 3,000 | ~45 sec | ~2-3 sec (if few changes) |
| 10,000 | ~150 sec | ~5-8 sec (if few changes) |

The mtime check is a simple `os.stat()` call (~0.1ms per file), vs reading file content (~5-50ms per file depending on size).

## Automation

Trigger indexing via:
- Cron job calling the API
- OpenClaw scheduled task
- Manual API call

## Migration

When deploying the updated indexer:

1. First run will be slow (needs to populate mtime for all existing records)
2. Subsequent runs will be fast (mtime-based skipping)

Alternative: Run one `full: true` reindex after deployment to populate all mtime values.

---

*Last updated: 2026-02-15*
