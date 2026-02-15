#!/usr/bin/env python3
"""
Daily Vault Sync - Reorganize + GPU Reindex

This script:
1. Checks for new/modified files (skip if none, unless --force)
2. Runs reorganize_v2.py to process new Granola notes (optional)
3. Wakes up GPU PC via WoL
4. Triggers GPU-accelerated reindex via Recall API
5. Shuts down GPU PC when complete

Usage:
    python daily_vault_sync.py           # Normal run (skip if no new files)
    python daily_vault_sync.py --force   # Force full reindex regardless of changes

Designed to be run daily via cron or OpenClaw scheduled task.
"""

import os
import sys
import time
import logging
import argparse
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
SKIP_REORGANIZE = os.environ.get("SKIP_REORGANIZE", "true").lower() == "true"  # Skip by default (flat structure)
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

# Vault paths (for pre-check) - must be set via environment variable
OBSIDIAN_WORK_PATH = Path(os.environ.get("OBSIDIAN_WORK_PATH", "./obsidian/work"))
LAST_INDEX_FILE = SCRIPT_DIR.parent / "logs" / ".last_index_time"


def check_for_new_files():
    """
    Check if there are new/modified files since last index.
    Returns (has_new_files, new_count, total_count).
    """
    logger.info("🔍 Checking for new/modified files...")
    
    # Get last index time
    last_index_time = 0
    if LAST_INDEX_FILE.exists():
        try:
            last_index_time = float(LAST_INDEX_FILE.read_text().strip())
            logger.info(f"Last index: {datetime.fromtimestamp(last_index_time).strftime('%Y-%m-%d %H:%M')}")
        except:
            pass
    
    # Scan vault for .md files
    new_files = []
    total_files = 0
    
    for md_file in OBSIDIAN_WORK_PATH.rglob("*.md"):
        total_files += 1
        try:
            mtime = md_file.stat().st_mtime
            if mtime > last_index_time:
                new_files.append(md_file)
        except:
            pass
    
    new_count = len(new_files)
    
    if new_count > 0:
        logger.info(f"📄 Found {new_count} new/modified files (out of {total_files} total)")
        # Log first few new files
        for f in new_files[:5]:
            logger.info(f"  - {f.name}")
        if new_count > 5:
            logger.info(f"  ... and {new_count - 5} more")
    else:
        logger.info(f"✅ No new files since last index ({total_files} files unchanged)")
    
    return new_count > 0, new_count, total_files


def save_index_timestamp():
    """Save current timestamp as last index time."""
    try:
        LAST_INDEX_FILE.write_text(str(time.time()))
        logger.info("📝 Saved index timestamp")
    except Exception as e:
        logger.warning(f"Could not save index timestamp: {e}")


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
    """Poll index progress until complete. Returns (success, files_processed)."""
    logger.info("📊 Monitoring index progress...")
    
    headers = {"Authorization": f"Bearer {RECALL_API_TOKEN}"}
    start = time.time()
    last_processed = 0
    
    while time.time() - start < GPU_INDEX_TIMEOUT:
        try:
            resp = requests.get(
                f"{RECALL_API_URL}/index/progress",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                processed = data.get("processed", 0)
                total = data.get("total", 0)
                
                # Check if job completed (status is "idle" or "completed", not "running")
                if status != "running":
                    if processed > 0:
                        logger.info(f"✅ Indexing complete! Processed {processed} files")
                        return True, processed
                    elif total == 0 and processed == 0:
                        # Job started but found no files - this is an error
                        logger.error(f"❌ Indexing completed but 0 files processed! Check vault path.")
                        return False, 0
                    else:
                        logger.info(f"✅ Indexing complete! Processed {processed} files")
                        return True, processed
                
                # Still running - log progress
                percent = data.get("percent", 0)
                eta = data.get("eta_human", "unknown")
                current = data.get("current_file", "")[:50]
                
                # Only log if progress changed
                if processed != last_processed:
                    logger.info(f"Progress: {percent:.1f}% ({processed}/{total}) | ETA: {eta} | {current}")
                    last_processed = processed
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Progress check failed: {e}")
        
        time.sleep(POLL_INTERVAL)
    
    logger.error(f"❌ Indexing timed out after {GPU_INDEX_TIMEOUT}s")
    return False, last_processed


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
    # Parse arguments
    parser = argparse.ArgumentParser(description="Daily Vault Sync - GPU-accelerated reindexing")
    parser.add_argument("--force", "-f", action="store_true", 
                        help="Force full reindex regardless of file changes")
    parser.add_argument("--skip-shutdown", action="store_true",
                        help="Don't shutdown GPU PC after indexing")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"🗓️  Daily Vault Sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.force:
        logger.info("⚡ FORCE MODE - will reindex all files")
    logger.info("=" * 60)
    
    # Step 1: Reorganize vault (optional - skipped by default for flat structure)
    if SKIP_REORGANIZE:
        logger.info("⏭️  Skipping reorganization (SKIP_REORGANIZE=true)")
    elif not run_reorganize():
        logger.error("Reorganization failed, aborting")
        return 1
    
    # Step 2: Check if there are new files to index (skip check if --force)
    if args.force:
        logger.info("🔄 Force mode: skipping new file check, will reindex everything")
        new_count = "all"
    else:
        has_new_files, new_count, total_count = check_for_new_files()
        
        if not has_new_files:
            logger.info("🎉 No new files to index - skipping GPU wake and reindex")
            logger.info("Daily vault sync completed (nothing to do)")
            return 0
        
        logger.info(f"📊 {new_count} files need indexing - proceeding with GPU reindex")
    
    # Step 3: Wake GPU PC
    if not wake_gpu_pc():
        logger.error("Failed to send WoL, aborting GPU reindex")
        return 1
    
    # Step 4: Wait for Ollama
    if not wait_for_gpu_ollama():
        logger.error("GPU Ollama not available, aborting")
        return 1
    
    # Step 5: Trigger reindex
    if not trigger_gpu_reindex():
        logger.error("Failed to trigger reindex")
        if not args.skip_shutdown:
            shutdown_gpu_pc()  # Still try to shutdown
        return 1
    
    # Step 6: Wait for completion
    success, files_processed = wait_for_index_complete()
    
    # Step 7: Shutdown GPU PC (unless --skip-shutdown)
    if args.skip_shutdown:
        logger.info("⏭️  Skipping GPU shutdown (--skip-shutdown flag)")
    else:
        shutdown_gpu_pc()
    
    # Validate results
    if not success:
        logger.error("❌ Daily vault sync FAILED - indexing did not complete successfully")
        return 1
    
    if files_processed == 0:
        logger.error("❌ Daily vault sync FAILED - 0 files were indexed (check vault path!)")
        return 1
    
    # Save timestamp for next run's comparison
    save_index_timestamp()
    
    logger.info(f"🎉 Daily vault sync completed successfully! Indexed {files_processed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
