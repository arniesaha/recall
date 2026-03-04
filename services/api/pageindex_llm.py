"""
PageIndex LLM Client

LLM client for PageIndex tree generation and search with fallback support.
Primary: Max (Mac Mini) - always on
Fallback: GPU PC (RTX 5090) - free but needs wake via WoL
"""

import asyncio
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class PageIndexLLM:
    """LLM client for PageIndex with automatic fallback."""
    
    def __init__(self):
        self.wol_url = settings.gpu_wol_server_url  # WoL server on NAS
    
    async def call(self, prompt: str, max_tokens: int = 4096) -> str:
        """
        Call LLM with automatic fallback chain.
        
        Order: Max (primary) → GPU PC (fallback)
        """
        errors = []
        
        # Primary: Max (Mac Mini)
        if settings.pageindex_llm_provider in ("max", "auto"):
            try:
                return await self._call_max(prompt, max_tokens)
            except Exception as e:
                logger.warning(f"Max unavailable: {e}")
                errors.append(f"max: {e}")
                if settings.pageindex_llm_provider == "max":
                    raise RuntimeError(f"Max LLM failed: {e}")
        
        # Fallback: GPU PC (free, local)
        if settings.pageindex_llm_provider in ("gpu", "auto"):
            try:
                await self._wake_gpu_if_needed()
                return await self._call_gpu(prompt, max_tokens)
            except Exception as e:
                logger.warning(f"GPU unavailable: {e}")
                errors.append(f"gpu: {e}")
                if settings.pageindex_llm_provider == "gpu":
                    raise RuntimeError(f"GPU LLM failed: {e}")
        
        raise RuntimeError(f"No LLM provider available. Errors: {errors}")
    
    async def _call_max(self, prompt: str, max_tokens: int = 4096) -> str:
        """Call Max's OpenClaw gateway (Claude on Mac Mini)."""
        if not settings.max_gateway_token:
            raise RuntimeError("MAX_GATEWAY_TOKEN not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.max_gateway_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.max_gateway_token}"},
                json={
                    "model": settings.max_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": max_tokens
                },
                timeout=180.0  # Allow longer for complex tree generation
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    async def _call_gpu(self, prompt: str, max_tokens: int = 4096) -> str:
        """Call GPU PC's Ollama (qwen2.5 or similar)."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.gpu_ollama_url}/v1/chat/completions",
                json={
                    "model": settings.gpu_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": max_tokens
                },
                timeout=300.0  # Longer timeout for local model
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    
    async def _wake_gpu_if_needed(self) -> bool:
        """Wake GPU PC via WoL server if not responding."""
        async with httpx.AsyncClient() as client:
            # Check if already awake
            try:
                await client.get(
                    f"{settings.gpu_ollama_url}/api/tags",
                    timeout=5.0
                )
                return True  # Already awake
            except:
                pass
            
            # Send WoL via NAS server
            logger.info("Waking GPU PC for PageIndex LLM...")
            try:
                await client.get(f"{self.wol_url}/wake", timeout=10.0)
            except Exception as e:
                logger.warning(f"WoL request failed: {e}")
                raise RuntimeError("Could not send WoL packet")
            
            # Wait for it to come up (max 90s)
            for i in range(18):
                await asyncio.sleep(5)
                try:
                    await client.get(
                        f"{settings.gpu_ollama_url}/api/tags",
                        timeout=5.0
                    )
                    logger.info(f"GPU PC is awake after ~{(i+1)*5}s")
                    return True
                except:
                    continue
            
            raise RuntimeError("GPU PC did not wake up in time (90s)")
    
    async def health_check(self) -> dict:
        """Check LLM provider health."""
        result = {
            "max": "unknown",
            "gpu": "unknown"
        }
        
        async with httpx.AsyncClient() as client:
            # Check Max
            try:
                if not settings.max_gateway_token:
                    result["max"] = "no_token"
                else:
                    resp = await client.get(
                        f"{settings.max_gateway_url}/health",
                        headers={"Authorization": f"Bearer {settings.max_gateway_token}"},
                        timeout=5.0
                    )
                    result["max"] = "ok" if resp.status_code == 200 else f"error_{resp.status_code}"
            except Exception as e:
                result["max"] = f"error: {str(e)[:50]}"
            
            # Check GPU
            try:
                resp = await client.get(
                    f"{settings.gpu_ollama_url}/api/tags",
                    timeout=5.0
                )
                result["gpu"] = "ok" if resp.status_code == 200 else f"error_{resp.status_code}"
            except Exception as e:
                result["gpu"] = f"offline: {str(e)[:30]}"
        
        return result


# Singleton instance
_llm_instance: Optional[PageIndexLLM] = None


def get_pageindex_llm() -> PageIndexLLM:
    """Get or create the PageIndex LLM client."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = PageIndexLLM()
    return _llm_instance
