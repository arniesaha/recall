#!/usr/bin/env python3
"""
GPU PC Shutdown Server
Listens on port 8765 and shuts down when called with correct token.

Install on GPU PC:
    chmod +x ~/shutdown-server.py
    sudo cp gpu-shutdown.service /etc/systemd/system/
    echo "arnab ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/shutdown
    sudo chmod 440 /etc/sudoers.d/shutdown
    sudo systemctl daemon-reload
    sudo systemctl enable gpu-shutdown
    sudo systemctl start gpu-shutdown
"""

import subprocess
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

PORT = 8765
SECRET = "gpu-shutdown-ok"  # Must match Recall API config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class ShutdownHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")
    
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "gpu-shutdown"})
        else:
            self._send_json({"error": "Use POST /shutdown"}, 404)
    
    def do_POST(self):
        if self.path != "/shutdown":
            self._send_json({"error": "Not found"}, 404)
            return
        
        # Check auth
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {SECRET}":
            logger.warning(f"Unauthorized shutdown attempt from {self.client_address[0]}")
            self._send_json({"error": "Unauthorized"}, 401)
            return
        
        logger.info("Shutdown requested - shutting down now...")
        self._send_json({"success": True, "message": "Shutting down now"})
        
        # Shutdown after response is sent
        subprocess.Popen(["sudo", "shutdown", "-h", "+0"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), ShutdownHandler)
    logger.info(f"Shutdown server running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped")
