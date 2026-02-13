#!/usr/bin/env python3
"""
WoL HTTP Server for GPU Offload

Relays Wake-on-LAN requests from k8s pods to the local network.
Needed because WoL broadcasts don't cross subnets.

Usage:
    python3 wol-server.py

Endpoints:
    GET /wake   - Send WoL packet to GPU PC
    GET /health - Check GPU PC reachability
    GET /status - Full status info
"""

import subprocess
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging

# ============== CONFIGURATION ==============
# Update these for your environment

PORT = 9753
GPU_PC_MAC = "aa:bb:cc:dd:ee:ff"      # GPU PC MAC address
GPU_PC_IP = "10.10.10.2"               # GPU PC IP (for health checks)
GPU_BROADCAST_IP = "10.10.10.255"      # Subnet broadcast IP (NOT 255.255.255.255)

# ===========================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def send_wol(mac_address: str) -> bool:
    """Send Wake-on-LAN magic packet."""
    try:
        # Try wakeonlan command with subnet broadcast IP
        result = subprocess.run(
            ["wakeonlan", "-i", GPU_BROADCAST_IP, mac_address],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info(f"WoL sent via wakeonlan -i {GPU_BROADCAST_IP} to {mac_address}")
            return True
    except FileNotFoundError:
        pass  # wakeonlan not installed, try manual
    except Exception as e:
        logger.warning(f"wakeonlan failed: {e}")
    
    # Manual WoL packet to subnet broadcast
    try:
        mac_bytes = bytes.fromhex(mac_address.replace(":", ""))
        magic = b'\xff' * 6 + mac_bytes * 16
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (GPU_BROADCAST_IP, 9))
        sock.close()
        logger.info(f"WoL sent manually to {mac_address} via {GPU_BROADCAST_IP}")
        return True
    except Exception as e:
        logger.error(f"Manual WoL failed: {e}")
        return False


def check_gpu_pc() -> bool:
    """Check if GPU PC is reachable (Ollama port)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((GPU_PC_IP, 11434))  # Ollama port
        sock.close()
        return result == 0
    except:
        return False


class WoLHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")
    
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        if self.path == "/wake":
            success = send_wol(GPU_PC_MAC)
            self._send_json({
                "success": success,
                "mac": GPU_PC_MAC,
                "message": "WoL packet sent" if success else "Failed to send WoL"
            })
        
        elif self.path == "/health":
            gpu_up = check_gpu_pc()
            self._send_json({
                "status": "ok",
                "gpu_pc_reachable": gpu_up,
                "gpu_pc_ip": GPU_PC_IP
            })
        
        elif self.path == "/status":
            gpu_up = check_gpu_pc()
            self._send_json({
                "gpu_pc": {
                    "mac": GPU_PC_MAC,
                    "ip": GPU_PC_IP,
                    "broadcast": GPU_BROADCAST_IP,
                    "ollama_reachable": gpu_up
                }
            })
        
        else:
            self._send_json({
                "error": "Not found", 
                "endpoints": ["/wake", "/health", "/status"]
            }, 404)
    
    def do_POST(self):
        # POST /wake also works
        if self.path == "/wake":
            self.do_GET()
        else:
            self._send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), WoLHandler)
    logger.info(f"WoL server starting on port {PORT}")
    logger.info(f"GPU PC: {GPU_PC_MAC} ({GPU_PC_IP}), broadcast: {GPU_BROADCAST_IP}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()
