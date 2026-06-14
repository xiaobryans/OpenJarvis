#!/bin/bash
# User data for openclaw-mobile on Ubuntu 22.04 with Python 3.10+
# Includes: SSM agent, Tailscale, OpenJarvis, status server

# Set hostname
hostnamectl set-hostname openclaw-mobile

# Update packages
apt-get update -y

# Install SSM agent (enables remote management via AWS SSM)
snap install amazon-ssm-agent --classic 2>/dev/null || true
systemctl enable snap.amazon-ssm-agent.amazon-ssm-agent.service 2>/dev/null || true
systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service 2>/dev/null || true

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install AWS CLI and Python tools
apt-get install -y awscli python3 python3-pip python3-venv git

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

# Create Python venv and install OpenJarvis + boto3
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -e . --quiet
pip install boto3 --quiet

# Create richer status/health endpoint
cat > /opt/jarvis_status.py << 'PYEOF'
#!/usr/bin/env python3
import http.server
import socketserver
import json
import subprocess
import platform
import os
import sys

PORT = 3091

def get_tailscale_ip():
    try:
        result = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True, timeout=3)
        return result.stdout.strip() if result.returncode == 0 else 'unknown'
    except Exception:
        return 'unknown'

def get_jarvis_version():
    try:
        venv_jarvis = '/opt/OpenJarvis/venv/bin/jarvis'
        result = subprocess.run([venv_jarvis, '--version'], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else 'unknown'
    except Exception:
        return 'installed'

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'hostname': 'openclaw-mobile',
                'runtime': 'OpenJarvis',
                'python': sys.version.split()[0],
                'tailscale_ip': get_tailscale_ip()
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/api/jarvis/status-bundle':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'schema': 'omnix.jarvis.status_bundle.v1',
                'hostname': 'openclaw-mobile',
                'runtime': 'OpenJarvis',
                'runtime_version': get_jarvis_version(),
                'python': sys.version.split()[0],
                'tailscale': 'connected',
                'tailscale_ip': get_tailscale_ip(),
                'storage': 'aws-s3',
                'storage_bucket': 'omnix-workbench-071179620006-ap-southeast-1-artifacts',
                'instance_type': 't3.micro',
                'os': 'Ubuntu 22.04',
                'cost_estimate': '$34.50-44.50/month'
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'openclaw-mobile Jarvis Runtime - use /health or /api/jarvis/status-bundle')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
    httpd.serve_forever()
PYEOF

chmod +x /opt/jarvis_status.py

# Create systemd service
cat > /etc/systemd/system/jarvis-status.service << 'SVCEOF'
[Unit]
Description=Jarvis Status Server
After=network.target tailscaled.service
Wants=tailscaled.service

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
