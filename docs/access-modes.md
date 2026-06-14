# Access Modes for Jarvis OMNIX Workbench

## Overview

This document describes the different access modes available for Jarvis OMNIX Workbench and Mission Control.

## Mode 1: Local Mac-Only Mode (Current Default)

### Description
Mission Control runs locally on the Mac, accessible only via localhost. This is the current working mode.

### Requirements
- Mac must be awake
- Mission Control bridge must be running
- Access only from Mac itself (localhost:3091)

### Commands
```bash
jarvis omnix mission-control start
jarvis omnix mission-control status
jarvis omnix mission-control stop
```

### Network Exposure
- **Bind Address**: `127.0.0.1` (localhost only)
- **Public Access**: None
- **Tailnet Access**: None

### Use Case
- Local development and testing
- Single-user workflow
- No mobile access required

## Mode 2: Tailnet Private Mac Mode

### Description
Mission Control runs locally on the Mac but is accessible via Tailscale private networking when Mac is awake.

### Requirements
- Mac must be awake
- Tailscale must be running and logged in
- Mac must be on Tailnet
- Mission Control bridge must be running

### Setup Commands
```bash
# Start Tailscale
sudo tailscale up

# Start Mission Control with Tailnet binding
OPENCLAW_WORKSPACE_DIR=/Users/user/CascadeProjects/openclaw-workspace-omnix \
  PORT=3091 \
  HOST=0.0.0.0 \
  node server.js
```

### Network Exposure
- **Bind Address**: `0.0.0.0` (all interfaces, but protected by Tailscale)
- **Public Access**: None (Tailscale private only)
- **Tailnet Access**: Yes (via Tailscale private IP)

### Security Considerations
- **Do not use Tailscale Funnel** (exposes publicly)
- **Configure ACLs** to restrict access to trusted devices
- **Use Tailscale SSH** for secure remote access
- **Keep Mac firewall enabled** for additional protection

### Use Case
- Access from other devices on same Tailnet
- Private access when Mac is awake
- No mobile access when Mac is off

### Limitations
- **Mobile without Mac on**: NOT SOLVED - Tailscale alone cannot provide mobile access without Mac awake
- Requires cloud node for true mobile access

## Mode 3: Cloud Node Tailnet Mode

### Description
Mission Control runs in the cloud (AWS) and is accessible via Tailscale private networking. This enables mobile access without Mac being awake.

### Requirements
- Cloud infrastructure deployed (AWS ECS/Lambda/EC2)
- Tailscale node running in cloud
- Cloud storage configured (S3/DynamoDB)
- Mac not required to be awake

### Architecture
- **Cloud Runtime**: AWS ECS Fargate or EC2
- **Storage**: Cloud-backed (S3 for artifacts, DynamoDB for state)
- **Networking**: VPC with Tailscale subnet router or DERP
- **Access**: Private via Tailscale only

### Network Exposure
- **Bind Address**: Cloud VPC private IP
- **Public Access**: None (private VPC + Tailscale)
- **Tailnet Access**: Yes (via Tailscale subnet router or DERP)

### Use Case
- Mobile access without Mac awake
- Always-available Mission Control
- Multi-user collaboration
- Cloud-backed persistence

### Cost
- **Minimum**: $50-200/month for cloud infrastructure
- **Tailscale**: Free for personal use, $6-100/month for business tier

### Deployment
- See `deploy/aws/README.md` for cloud deployment instructions
- Requires explicit approval and budget authorization

## Why Tailscale Alone Cannot Solve Mobile Without Mac On

Tailscale provides private networking between devices, but it does not provide cloud hosting:

1. **Tailscale is a networking layer**, not a hosting platform
2. **Devices must be online** to be accessible via Tailnet
3. **Mac must be awake** to host Mission Control bridge
4. **No cloud runtime** - Tailscale doesn't host applications
5. **No cloud storage** - Tailscale doesn't provide database/storage

**To enable mobile without Mac on, you need:**
- Cloud-hosted Jarvis/OpenClaw/Mission Control runtime (AWS ECS/Lambda/EC2)
- Cloud-backed persistence (S3/DynamoDB)
- Tailscale can then provide private access to the cloud runtime
- Mobile devices connect to cloud node via Tailscale

## Current Status

### Tailscale Status
- **Installation**: Installed (version 1.98.5)
- **Running**: Stopped
- **Tailnet**: Not configured
- **ACLs**: Default (not configured)

### Required for Mode 2 (Tailnet Private Mac)
1. Start Tailscale: `sudo tailscale up`
2. Configure ACLs (if needed) via Tailscale admin console
3. Modify Mission Control bind address to `0.0.0.0`
4. Configure firewall to allow Tailscale connections

### Required for Mode 3 (Cloud Node Tailnet)
1. Deploy cloud infrastructure (see `deploy/aws/README.md`)
2. Install Tailscale on cloud instances
3. Configure Tailscale subnet router or DERP
4. Update Mission Control to use cloud storage
5. Configure mobile devices with Tailscale

## Security Best Practices

### For All Modes
- Never expose Mission Control publicly (no `0.0.0.0` without protection)
- Never use Tailscale Funnel (exposes to public internet)
- Always use HTTPS/TLS for network traffic
- Never commit secrets or credentials
- Use strong authentication for admin access

### For Tailnet Modes
- Configure ACLs to restrict access to trusted devices
- Use Tailscale SSH for secure remote access
- Enable key expiry and rotation
- Monitor access logs
- Regularly review device list

### For Cloud Mode
- Use private VPC subnets
- No public internet gateway access
- Use IAM roles and least privilege
- Enable CloudTrail for audit logging
- Use AWS Secrets Manager for credentials
- Enable security groups with restrictive rules

## Migration Path

### From Local to Tailnet Private Mac
1. Install and start Tailscale on Mac
2. Configure Tailscale ACLs (if needed)
3. Update Mission Control bind address to `0.0.0.0`
4. Test access from other Tailnet devices
5. Roll back to `127.0.0.1` if needed

### From Local to Cloud Node
1. Review and approve cloud deployment architecture
2. Deploy AWS infrastructure (see `deploy/aws/README.md`)
3. Configure cloud storage and migration
4. Install Tailscale on cloud instances
5. Configure Tailscale subnet router or DERP
6. Test access from mobile devices
7. Migrate local data to cloud (with approval)
8. Update clients to use cloud endpoint

## Troubleshooting

### Tailscale Connection Issues
```bash
# Check Tailscale status
tailscale status

# Check Tailscale logs
tailscale bugreport

# Restart Tailscale
sudo tailscale down
sudo tailscale up

# Check firewall
sudo ufw status  # Linux
sudo pfctl -s rules  # macOS
```

### Mission Control Access Issues
```bash
# Check if bridge is running
jarvis omnix mission-control status

# Check port binding
lsof -i:3091

# Check firewall rules
sudo pfctl -s rules  # macOS

# Test local access
curl http://127.0.0.1:3091/api/jarvis/status-bundle

# Test Tailnet access
curl http://<tailscale-ip>:3091/api/jarvis/status-bundle
```

## Summary Table

| Mode | Mac Required Awake | Mobile Access | Cloud Required | Cost | Complexity |
|------|-------------------|---------------|----------------|------|------------|
| Local Mac-Only | Yes | No | No | Free | Low |
| Tailnet Private Mac | Yes | No (Mac required) | No | Free | Medium |
| Cloud Node Tailnet | No | Yes (via Tailnet) | Yes | $50-200/month | High |

## Recommendations

### For Local Development
- Use **Local Mac-Only mode** (current default)
- Simple, no additional setup required
- Suitable for single-user workflow

### For Private Team Access
- Use **Tailnet Private Mac mode**
- Requires Mac to be awake
- Suitable for small team with Mac always-on
- No cloud costs

### For Full Mobile Access
- Use **Cloud Node Tailnet mode**
- Requires cloud infrastructure deployment
- Enables mobile without Mac on
- Suitable for production/multi-user
- Requires budget approval and setup

## Next Steps

1. **Current**: Continue using Local Mac-Only mode
2. **If Tailnet access needed**: Configure Tailscale and update Mission Control binding
3. **If mobile access needed**: Review cloud deployment plan and obtain approval
4. **Always**: Test access changes in development before production
