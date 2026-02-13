# GPU Offload for Recall Indexing

Recall supports offloading embedding generation to a remote GPU machine for faster indexing (~50 vectors/sec vs ~2/sec on CPU).

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Recall API    │────▶│   WoL Server    │────▶│    GPU PC       │
│   (k8s pod)     │     │   (NAS host)    │     │  (Ollama GPU)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │              HTTP (embed API)                 │
        └───────────────────────────────────────────────┘
```

## Components

### 1. WoL HTTP Server (NAS Host)

Simple HTTP server that sends Wake-on-LAN packets to the GPU PC.

**Location:** `scripts/wol-server.py`

**Why needed:** k8s pods are on a different subnet (10.42.x.x) than the GPU PC (10.10.10.x). WoL broadcasts don't cross subnets, so we relay through the NAS host.

**Endpoints:**
- `GET /wake` - Send WoL magic packet
- `GET /health` - Check if GPU PC is reachable
- `GET /status` - Full status info

**Configuration:**
- Port: 9753
- Broadcast IP: Must match GPU PC's subnet (e.g., `10.10.10.255`)

### 2. GPU Shutdown Server (GPU PC)

HTTP server on the GPU PC that accepts authenticated shutdown requests.

**Location:** `scripts/gpu-shutdown-server.py`

**Endpoints:**
- `GET /health` - Health check
- `POST /shutdown` - Shutdown PC (requires Bearer token)

**Security:** Requires `Authorization: Bearer <token>` header.

### 3. Recall API GPU Offload

The Recall API automatically:
1. Checks if GPU Ollama is already available
2. If not, calls WoL server to wake the GPU PC
3. Waits for Ollama to become healthy (configurable timeout)
4. Routes embedding requests to GPU Ollama
5. Falls back to CPU Ollama if GPU unavailable

## Configuration

Environment variables / config:

```python
# GPU Offload settings
gpu_ollama_url: str = "http://<gpu-pc-ip>:11434"
gpu_ollama_enabled: bool = True
gpu_wol_mac: str = "<gpu-pc-mac>"
gpu_wol_server_url: str = "http://<nas-ip>:9753"
gpu_boot_wait_seconds: int = 5
gpu_health_timeout_seconds: int = 120
gpu_auto_shutdown: bool = True
gpu_shutdown_url: str = "http://<gpu-pc-ip>:8765/shutdown"
gpu_shutdown_secret: str = "<secret-token>"
```

## Usage

### Trigger GPU Indexing

```bash
curl -X POST \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  -d '{"rebuild": true, "use_gpu": true}' \
  https://recallapi.example.com/index/start
```

### Monitor Progress

```bash
curl -H "Authorization: Bearer <api-token>" \
  https://recallapi.example.com/index/progress
```

## Setup Instructions

### NAS Host (WoL Server)

1. Copy `scripts/wol-server.py` to NAS
2. Update `GPU_BROADCAST_IP` to match your GPU PC's subnet
3. Install as systemd service:
   ```bash
   sudo cp wol-server.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable wol-server
   sudo systemctl start wol-server
   ```

### GPU PC (Shutdown Server)

See `scripts/GPU-SETUP.md` for detailed instructions.

Key steps:
1. Enable Wake-on-LAN in BIOS
2. Configure network interface for WoL: `sudo ethtool -s <interface> wol g`
3. Install shutdown server as systemd service
4. Configure passwordless shutdown via sudoers

## Metrics

Prometheus metrics for monitoring:

- `recall_index_job_running` - Whether indexing is active (0/1)
- `recall_index_progress_percent` - Current progress (0-100)
- `recall_index_total_files` - Total files to index
- `recall_index_processed_files` - Files processed
- `recall_index_eta_seconds` - Estimated time remaining

## Troubleshooting

### WoL not waking PC

1. Check broadcast IP matches GPU PC's subnet
2. Verify WoL enabled in GPU PC BIOS
3. Check network interface WoL setting: `ethtool <interface> | grep Wake`
4. Test manually: `wakeonlan -i <broadcast-ip> <mac>`

### GPU fallback to CPU

Check logs for:
- "GPU PC did not wake, falling back to CPU"
- Timeout waiting for Ollama

Increase `gpu_health_timeout_seconds` if PC needs more boot time.
