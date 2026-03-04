# Scripts

Utility scripts for Recall.

## Available Scripts

### daily_vault_sync.py

Triggers FTS reindexing of the vault via the API.

```bash
RECALL_API_TOKEN=your-token python daily_vault_sync.py
```

### wol-server.py

Wake-on-LAN HTTP server — sends magic packets to wake machines on the network.

```bash
python wol-server.py
# POST http://localhost:9753/wake {"mac": "AA:BB:CC:DD:EE:FF"}
```

### gpu-shutdown-server.py

HTTP endpoint to remotely shut down a machine (used for GPU PC power management).

```bash
GPU_SHUTDOWN_SECRET=your-secret python gpu-shutdown-server.py
# POST http://localhost:8765/shutdown (Authorization: Bearer your-secret)
```

### reorganize_v2.py

Reorganizes Obsidian vault files into a structured folder hierarchy.
