# Scripts

Utility scripts for Recall.

## Configuration

All scripts use environment variables for paths. Set them in your `.env` file or export them:

```bash
export OBSIDIAN_WORK_PATH=/path/to/your/obsidian/work
export VAULT_PATH=/path/to/your/obsidian/work
```

See `../.env.example` for all available options.

## Available Scripts

### daily_vault_sync.py

Main synchronization script. Wakes GPU PC, triggers indexing, and monitors progress.

```bash
python3 scripts/daily_vault_sync.py
```

### reorganize_v2.py

Vault reorganization tool. Consolidates duplicate folders, improves categorization.

```bash
python3 scripts/reorganize_v2.py --dry-run  # Preview changes
python3 scripts/reorganize_v2.py            # Apply changes
```

## Infrastructure Scripts

### gpu-shutdown-server.py

HTTP server for remote GPU PC shutdown. See `GPU-SETUP.md` for setup.

### wol-server.py

Wake-on-LAN server for waking the GPU PC remotely.

## Automation

Set up a cron job or use the Recall API's built-in scheduling.
