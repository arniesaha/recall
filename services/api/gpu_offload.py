"""
GPU Offload Helper

Handles Wake-on-LAN and health checking for remote GPU-enabled Ollama.
"""

import asyncio
import logging
import subprocess
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


async def send_wol(
    mac_address: str, 
    broadcast_ip: str = "255.255.255.255", 
    wol_server_url: str = None
) -> bool:
    """
    Send Wake-on-LAN magic packet via HTTP WoL server.
    
    Args:
        mac_address: Target MAC (e.g., "60:cf:84:cb:3f:aa")
        broadcast_ip: Broadcast IP for the subnet (unused now)
        wol_server_url: WoL HTTP server URL on host (e.g., "http://192.168.1.70:9753")
    
    Returns:
        True if WoL packet sent successfully
    """
    # Use WoL HTTP server on host (works from inside k8s)
    if wol_server_url:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{wol_server_url}/wake", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        logger.info(f"WoL triggered via host server: {data}")
                        return True
                    else:
                        logger.warning(f"WoL server reported failure: {data}")
                else:
                    logger.warning(f"WoL server request failed: {response.status_code}")
        except Exception as e:
            logger.error(f"WoL server request failed: {e}")
        return False
    
    # Fallback: try local wakeonlan command (only works with hostNetwork)
    try:
        result = subprocess.run(
            ["wakeonlan", "-i", broadcast_ip, mac_address],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"WoL packet sent to {mac_address} via {broadcast_ip}")
            return True
        
        # Fallback: try etherwake
        result = subprocess.run(
            ["etherwake", "-b", mac_address],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"WoL packet sent to {mac_address} via etherwake")
            return True
            
        logger.warning(f"WoL command failed: {result.stderr}")
        return False
        
    except FileNotFoundError:
        logger.error("wakeonlan/etherwake not installed. Install with: apt install wakeonlan")
        return False
    except Exception as e:
        logger.error(f"WoL failed: {e}")
        return False


async def check_ollama_health(ollama_url: str, timeout: float = 5.0) -> bool:
    """
    Check if Ollama is responding.
    
    Args:
        ollama_url: Base URL (e.g., "http://10.10.10.2:11434")
        timeout: Request timeout in seconds
    
    Returns:
        True if Ollama is healthy
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=timeout)
            return response.status_code == 200
    except Exception:
        return False


async def wait_for_ollama(
    ollama_url: str,
    timeout_seconds: int = 120,
    poll_interval: float = 5.0
) -> bool:
    """
    Wait for Ollama to become available.
    
    Args:
        ollama_url: Base URL to check
        timeout_seconds: Max time to wait
        poll_interval: Time between checks
    
    Returns:
        True if Ollama became available, False if timeout
    """
    logger.info(f"Waiting for Ollama at {ollama_url} (timeout: {timeout_seconds}s)")
    
    elapsed = 0
    while elapsed < timeout_seconds:
        if await check_ollama_health(ollama_url):
            logger.info(f"Ollama is ready at {ollama_url} (took {elapsed}s)")
            return True
        
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        
        if elapsed % 15 == 0:  # Log every 15 seconds
            logger.info(f"Still waiting for Ollama... ({elapsed}s / {timeout_seconds}s)")
    
    logger.error(f"Timeout waiting for Ollama at {ollama_url}")
    return False


async def wake_and_wait(
    mac_address: str,
    ollama_url: str,
    broadcast_ip: str = "255.255.255.255",
    boot_wait_seconds: int = 45,
    health_timeout_seconds: int = 120,
    wol_server_url: str = None
) -> bool:
    """
    Wake PC via WoL and wait for Ollama to be ready.
    
    Args:
        mac_address: Target MAC address
        ollama_url: Ollama URL to health check
        broadcast_ip: WoL broadcast IP
        boot_wait_seconds: Initial wait after WoL for PC to boot
        health_timeout_seconds: Max time to wait for Ollama health
        wol_server_url: WoL HTTP server URL on host
    
    Returns:
        True if Ollama is ready, False otherwise
    """
    # First check if already awake
    if await check_ollama_health(ollama_url, timeout=3.0):
        logger.info("GPU Ollama already awake!")
        return True
    
    # Send WoL via host server
    logger.info(f"Waking GPU PC ({mac_address})...")
    wol_sent = await send_wol(mac_address, broadcast_ip, wol_server_url=wol_server_url)
    
    if not wol_sent:
        logger.warning("WoL may have failed, but continuing to wait...")
    
    # Initial boot wait
    logger.info(f"Waiting {boot_wait_seconds}s for PC to boot...")
    await asyncio.sleep(boot_wait_seconds)
    
    # Wait for Ollama to respond
    return await wait_for_ollama(ollama_url, health_timeout_seconds)


async def shutdown_gpu_pc(
    shutdown_url: str = "http://10.10.10.2:8765/shutdown",
    secret: str = "gpu-shutdown-ok"
) -> bool:
    """
    Send shutdown request to GPU PC.
    
    Args:
        shutdown_url: URL of the shutdown server
        secret: Auth token
    
    Returns:
        True if shutdown request accepted
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                shutdown_url,
                headers={"Authorization": f"Bearer {secret}"},
                timeout=10.0
            )
            if response.status_code == 200:
                logger.info("GPU PC shutdown requested successfully")
                return True
            else:
                logger.warning(f"GPU PC shutdown failed: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Failed to shutdown GPU PC: {e}")
        return False


async def ensure_model_loaded(ollama_url: str, model: str) -> bool:
    """
    Ensure a specific model is loaded in Ollama.
    
    Args:
        ollama_url: Ollama base URL
        model: Model name (e.g., "nomic-embed-text")
    
    Returns:
        True if model is available
    """
    try:
        async with httpx.AsyncClient() as client:
            # Check if model exists
            response = await client.get(f"{ollama_url}/api/tags", timeout=10.0)
            if response.status_code != 200:
                return False
            
            data = response.json()
            models = [m["name"].split(":")[0] for m in data.get("models", [])]
            
            if model in models or model.split(":")[0] in models:
                logger.info(f"Model {model} available on GPU Ollama")
                return True
            
            # Try to pull the model
            logger.info(f"Pulling model {model} on GPU Ollama...")
            response = await client.post(
                f"{ollama_url}/api/pull",
                json={"name": model},
                timeout=300.0  # 5 min timeout for pull
            )
            return response.status_code == 200
            
    except Exception as e:
        logger.error(f"Failed to ensure model: {e}")
        return False
