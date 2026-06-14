#!/bin/bash
# Simplified user data for openclaw-mobile Tailscale node

# Set hostname
hostnamectl set-hostname openclaw-mobile

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Install AWS CLI for secret retrieval
yum install -y awscli

# Get Tailscale auth key from Secrets Manager
TS_AUTHKEY=$(aws secretsmanager get-secret-value --secret-id omnix-workbench-tailscale-authkey --region ap-southeast-1 --query SecretString --output text)

# Start Tailscale daemon with userspace networking
tailscaled --tun=userspace-networking &
sleep 3

# Connect to Tailnet
tailscale up --authkey "$TS_AUTHKEY" --hostname openclaw-mobile

# Create simple status server
cat > /opt/status_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import json
import subprocess

PORT = 3091

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'hostname': 'openclaw-mobile'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(("0.0.0.0", PORT), StatusHandler) as httpd:
    print(f"Status server running on port {PORT}")
    httpd.serve_forever()
EOF

chmod +x /opt/status_server.py

# Create systemd service
cat > /etc/systemd/system/status-server.service << 'EOF'
[Unit]
Description=Status Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/status_server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable status-server.service
systemctl start status-server.service
