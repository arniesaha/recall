#!/usr/bin/env python3
"""
Daily Vault Sync - Reorganize + GPU Reindex

This script:
1. Runs reorganize_v2.py to process new Granola notes
2. Wakes up GPU PC via WoL
3. Triggers GPU-accelerated reindex via Recall API
4. Shuts down GPU PC when complete

Designed to be run daily via cron or OpenClaw scheduled task.
"""

import os
import sys
import time
import logging
import requests
from pathlib import Path
from datetime import datetime

# Add scripts dir to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Configure logging
LOG_DIR = SCRIPT_DIR.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'daily_vault_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WOL_SERVER_URL = os.environ.get("WOL_SERVER_URL", "http://192.168.1.70:9753")
GPU_PC_MAC = os.environ.get("GPU_PC_MAC", "60:cf:84:cb:3f:aa")
GPU_PC_IP = os.environ.get("GPU_PC_IP", "10.10.10.2")
OLLAMA_PORT = 11434

# Use NodePort (stable) instead of ClusterIP (can change on pod restart)
RECALL_API_URL = os.environ.get("RECALL_API_URL", "http://192.168.1.70:30889")
RECALL_API_TOKEN = os.environ.get("RECALL_API_TOKEN", "7a2953e9c597afe9c3f16c5b58a3c0eeba87cdb311a46103")

SHUTDOWN_SERVER_URL = f"http://{GPU_PC_IP}:8765"
SHUTDOWN_TOKEN = os.environ.get("SHUTDOWN_TOKEN", "gpu-shutdown-ok")

# Timeouts
GPU_WAKE_TIMEOUT = 180  # 3 minutes to wake
GPU_INDEX_TIMEOUT = 1800  # 30 minutes max for indexing
POLL_INTERVAL = 30  # Check progress every 30s


def run_reorganize():
    """Run the reorganize_v2.py script."""
    logger.info("🔄 Running vault reorganization...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "reorganize_v2.py"), "--apply"],
        capture_output=True,
        text=True,
        cwd=str(SCRIPT_DIR.parent)
    )
    
    if result.returncode != 0:
        logger.error(f"Reorganization failed: {result.stderr}")
        return False
    
    # Count actions from output
    lines = result.stdout.split('\n')
    for line in lines:
        if 'Total actions:' in line:
            logger.info(f"✅ Reorganization complete - {line.strip()}")
            break
    
    return True


def wake_gpu_pc():
    """Wake GPU PC via WoL server."""
    logger.info(f"⚡ Sending Wake-on-LAN to GPU PC ({GPU_PC_MAC})...")
    
    try:
        resp = requests.post(
            f"{WOL_SERVER_URL}/wake",
            json={"mac": GPU_PC_MAC},
            timeout=10
        )
        if resp.status_code == 200:
            logger.info("WoL packet sent successfully")
            return True
        else:
            logger.error(f"WoL server error: {resp.status_code} - {resp.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to contact WoL server: {e}")
        return False


def wait_for_gpu_ollama():
    """Wait for GPU PC's Ollama to become available."""
    logger.info(f"⏳ Waiting for GPU Ollama at {GPU_PC_IP}:{OLLAMA_PORT}...")
    
    start = time.time()
    ollama_url = f"http://{GPU_PC_IP}:{OLLAMA_PORT}/api/tags"
    
    while time.time() - start < GPU_WAKE_TIMEOUT:
        try:
            resp = requests.get(ollama_url, timeout=5)
            if resp.status_code == 200:
                logger.info("✅ GPU Ollama is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(5)
    
    logger.error(f"❌ GPU Ollama not available after {GPU_WAKE_TIMEOUT}s")
    return False


def trigger_gpu_reindex():
    """Trigger reindex via Recall API with GPU offload."""
    logger.info("🚀 Triggering GPU-accelerated reindex...")
    
    headers = {
        "Authorization": f"Bearer {RECALL_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Start full reindex with GPU offload
        resp = requests.post(
            f"{RECALL_API_URL}/index/start",
            json={"full": True, "use_gpu": True},
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Reindex started: {data}")
            return True
        else:
            logger.error(f"Failed to start reindex: {resp.status_code} - {resp.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return False


def wait_for_index_complete():
    """Poll index progress until complete."""
    logger.info("📊 Monitoring index progress...")
    
    headers = {"Authorization": f"Bearer {RECALL_API_TOKEN}"}
    start = time.time()
    
    while time.time() - start < GPU_INDEX_TIMEOUT:
        try:
            resp = requests.get(
                f"{RECALL_API_URL}/index/progress",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                
                if not data.get("running", False):
                    logger.info(f"✅ Indexing complete! Processed {data.get('processed', '?')} files")
                    return True
                
                percent = data.get("percent", 0)
                eta = data.get("eta_human", "unknown")
                current = data.get("current_file", "")[:50]
                logger.info(f"Progress: {percent:.1f}% | ETA: {eta} | {current}")
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Progress check failed: {e}")
        
        time.sleep(POLL_INTERVAL)
    
    logger.error(f"❌ Indexing timed out after {GPU_INDEX_TIMEOUT}s")
    return False


def shutdown_gpu_pc():
    """Shutdown GPU PC via shutdown server."""
    logger.info("🔌 Shutting down GPU PC...")
    
    try:
        resp = requests.post(
            f"{SHUTDOWN_SERVER_URL}/shutdown",
            headers={"Authorization": f"Bearer {SHUTDOWN_TOKEN}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            logger.info("✅ GPU PC shutdown initiated")
            return True
        else:
            logger.warning(f"Shutdown request returned: {resp.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not reach shutdown server: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info(f"🗓️  Daily Vault Sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)
    
    # Step 1: Reorganize vault
    if not run_reorganize():
        logger.error("Reorganization failed, aborting")
        return 1
    
    # Step 2: Wake GPU PC
    if not wake_gpu_pc():
        logger.error("Failed to send WoL, aborting GPU reindex")
        return 1
    
    # Step 3: Wait for Ollama
    if not wait_for_gpu_ollama():
        logger.error("GPU Ollama not available, aborting")
        return 1
    
    # Step 4: Trigger reindex
    if not trigger_gpu_reindex():
        logger.error("Failed to trigger reindex")
        shutdown_gpu_pc()  # Still try to shutdown
        return 1
    
    # Step 5: Wait for completion
    success = wait_for_index_complete()
    
    # Step 6: Shutdown GPU PC
    shutdown_gpu_pc()
    
    if success:
        logger.info("🎉 Daily vault sync completed successfully!")
        return 0
    else:
        logger.error("Daily vault sync completed with errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
