#!/bin/bash
# User data for openclaw-mobile Tailscale node

# Set hostname
hostnamectl set-hostname openclaw-mobile

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install Python 3 and AWS CLI
yum install -y python3 python3-pip
pip3 install --no-cache-dir awscli

# Create minimal runtime script
cat > /opt/mobile_runtime.py << 'EOF'
#!/usr/bin/env python3
"""
Minimal mobile runtime for Tailscale access
"""
import logging
import os
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = 3091

def get_tailscale_status():
    """Get Tailscale status."""
    try:
        result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Failed to get Tailscale status: {e}")
        return None

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'hostname': 'openclaw-mobile',
                'tailscale': get_tailscale_status() is not None
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            ts_status = get_tailscale_status()
            response = {
                'hostname': 'openclaw-mobile',
                'tailscale': ts_status,
                'uptime': time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info(f"{self.address_string} - {format % args}")

def start_tailscale():
    """Start Tailscale with auth key from Secrets Manager."""
    import boto3
    
    try:
        client = boto3.client('secretsmanager', region_name='ap-southeast-1')
        response = client.get_secret_value(SecretId='omnix-workbench-tailscale-authkey')
        authkey = response['SecretString']
        
        logger.info("Starting Tailscale daemon...")
        subprocess.run(['tailscaled', '--tun=userspace-networking'], check=True, background=True)
        time.sleep(3)
        
        logger.info("Connecting to Tailnet...")
        subprocess.run(['tailscale', 'up', '--authkey', authkey, '--hostname', 'openclaw-mobile'], check=True)
        logger.info("Tailscale connected successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start Tailscale: {e}")
        return False

def main():
    logger.info("Starting mobile runtime...")
    
    # Start Tailscale
    start_tailscale()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', PORT), StatusHandler)
    logger.info(f"Status server listening on port {PORT}")
    server.serve_forever()

if __name__ == '__main__':
    main()
EOF

chmod +x /opt/mobile_runtime.py

# Create systemd service
cat > /etc/systemd/system/mobile-runtime.service << 'EOF'
[Unit]
Description=Mobile Runtime Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/mobile_runtime.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mobile-runtime.service
systemctl start mobile-runtime.service
