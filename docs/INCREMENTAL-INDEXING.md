# Incremental Indexing Design

## Overview

The indexing system supports both full reindex and incremental indexing. The **n8n workflow does not need to change** — it continues to call `/index/start`, and the backend determines whether to do a full or incremental index based on the `full` parameter.

## API Contract (Unchanged)

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

The n8n workflow should use `full: false` for regular scheduled syncs.

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

Current implementation doesn't handle deletions. Enhancement:

1. Build set of all files currently on disk
2. Query index for all indexed file paths
3. Find files in index but not on disk → delete from index

## Schema Changes

Add `mtime` field to `DocumentChunk`:

```python
class DocumentChunk(LanceModel):
    id: str
    vector: Vector(768)
    file_path: str
    file_hash: str
    mtime: float              # NEW: file modification time (Unix timestamp)
    title: str
    # ... rest unchanged
```

## Performance

| Files | Current (read all) | Optimized (mtime check) |
|-------|-------------------|-------------------------|
| 3,000 | ~45 sec | ~2-3 sec (if few changes) |
| 10,000 | ~150 sec | ~5-8 sec (if few changes) |

The mtime check is a simple `os.stat()` call (~0.1ms per file), vs reading file content (~5-50ms per file depending on size).

## n8n Workflow

No changes required. The workflow continues to:

1. Trigger on schedule (e.g., every 6h) or webhook
2. Call `POST /index/start` with `full: false`
3. Receive callback on completion
4. (Optional) Send notification on failure

## Migration

When deploying the updated indexer:

1. First run will be slow (needs to populate mtime for all existing records)
2. Subsequent runs will be fast (mtime-based skipping)

Alternative: Run one `full: true` reindex after deployment to populate all mtime values.

---

*Last updated: 2026-02-11*
