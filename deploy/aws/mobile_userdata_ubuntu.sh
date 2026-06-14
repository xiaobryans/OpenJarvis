#!/bin/bash
# User data for openclaw-mobile on Ubuntu 22.04 with Python 3.10+

# Set hostname
hostnamectl set-hostname openclaw-mobile

# Update packages
apt-get update -y

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install AWS CLI
apt-get install -y awscli

# Install Python 3.10+ and development tools
apt-get install -y python3 python3-pip python3-venv git

# Verify Python version
python3 --version

# Get Tailscale auth key from Secrets Manager
TS_AUTHKEY=$(aws secretsmanager get-secret-value --secret-id omnix-workbench-tailscale-authkey --region ap-southeast-1 --query SecretString --output text)

# Start Tailscale daemon with userspace networking
tailscaled --tun=userspace-networking &
sleep 3

# Connect to Tailnet
tailscale up --authkey "$TS_AUTHKEY" --hostname openclaw-mobile

# Install OpenJarvis
cd /opt
git clone https://github.com/xiaobryans/OpenJarvis.git
cd OpenJarvis
git checkout localhost-get-tool

# Create Python venv with Python 3.10+
python3 -m venv venv
source venv/bin/activate

# Upgrade pip and install OpenJarvis
pip install --upgrade pip
pip install -e .

# Create status/health endpoint
cat > /opt/jarvis_status.py << 'PYEOF'
#!/usr/bin/env python3
import http.server
import socketserver
import json

PORT = 3091

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'hostname': 'openclaw-mobile', 'runtime': 'OpenJarvis'}
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/api/jarvis/status-bundle':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'hostname': 'openclaw-mobile', 'runtime': 'OpenJarvis', 'tailscale': 'connected', 'storage': 'local'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
    print(f"Jarvis status server running on port {PORT}")
    httpd.serve_forever()
PYEOF

chmod +x /opt/jarvis_status.py

# Create systemd service
cat > /etc/systemd/system/jarvis-status.service << 'SVCEOF'
[Unit]
Description=Jarvis Status Server
After=network.target tailscaled.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/jarvis_status.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable jarvis-status.service
systemctl start jarvis-status.service
