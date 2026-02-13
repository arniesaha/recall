#!/usr/bin/env python3
"""
Simple HTTP server that accepts shutdown requests.
Run this on your GPU PC to allow remote shutdown.

Usage:
    python3 pc-shutdown-server.py

Then the NAS can call:
    curl -X POST http://10.10.10.2:8765/shutdown
"""

import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = 8765
SECRET = "gpu-shutdown-ok"  # Simple auth token

class ShutdownHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/shutdown':
            # Optional: check auth header
            auth = self.headers.get('Authorization', '')
            if auth != f'Bearer {SECRET}':
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error": "unauthorized"}')
                return
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "shutting_down"}')
            
            print("Shutdown requested, shutting down in 5 seconds...")
            # Use subprocess to shutdown after response is sent
            subprocess.Popen(['sudo', 'shutdown', '-h', '+1'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

if __name__ == '__main__':
    print(f"Starting shutdown server on port {PORT}...")
    print(f"Health check: curl http://localhost:{PORT}/health")
    print(f"Shutdown: curl -X POST -H 'Authorization: Bearer {SECRET}' http://localhost:{PORT}/shutdown")
    
    server = HTTPServer(('0.0.0.0', PORT), ShutdownHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
