# GPU PC Setup for Recall

Scripts for the GPU PC to enable remote shutdown after indexing.

## Files
- `gpu-shutdown-server.py` — HTTP server that accepts shutdown requests
- `gpu-shutdown.service` — systemd service file

## Installation (on GPU PC)

```bash
# 1. Copy files
cp gpu-shutdown-server.py ~/shutdown-server.py
chmod +x ~/shutdown-server.py

# 2. Allow passwordless shutdown
echo "arnab ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/shutdown
sudo chmod 440 /etc/sudoers.d/shutdown

# 3. Install systemd service
sudo cp gpu-shutdown.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/gpu-shutdown.service
sudo systemctl daemon-reload
sudo systemctl enable gpu-shutdown
sudo systemctl start gpu-shutdown

# 4. Verify
curl http://localhost:8765/health
# Should return: {"status": "ok", "service": "gpu-shutdown"}
```

## Testing

From NAS:
```bash
# Check health
curl http://10.10.10.2:8765/health

# Trigger shutdown (use with caution!)
curl -X POST -H "Authorization: Bearer gpu-shutdown-ok" http://10.10.10.2:8765/shutdown
```

## Security

- Only accepts POST with correct Bearer token
- Token: `gpu-shutdown-ok` (matches Recall API config)
- Only accessible from local network
