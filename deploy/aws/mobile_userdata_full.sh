#!/bin/bash
# Full user data for openclaw-mobile with OpenJarvis runtime

# Set hostname
hostnamectl set-hostname openclaw-mobile

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install AWS CLI for secret retrieval
yum install -y awscli

# Install SSM agent for remote access
yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# Install Python 3, git, and development tools
yum install -y python3 python3-pip python3-devel git gcc

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

# Create Python venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e .

# Create minimal status/health endpoint
cat > /opt/jarvis_status.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import json
import subprocess
import os

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
            response = {
                'hostname': 'openclaw-mobile',
                'runtime': 'OpenJarvis',
                'tailscale': 'connected',
                'storage': 'local'
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs

with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
    print(f"Jarvis status server running on port {PORT}")
    httpd.serve_forever()
EOF

chmod +x /opt/jarvis_status.py

# Create systemd service for status server
cat > /etc/systemd/system/jarvis-status.service << 'EOF'
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
EOF

systemctl daemon-reload
systemctl enable jarvis-status.service
systemctl start jarvis-status.service
