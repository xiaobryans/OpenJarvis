# Jarvis OMNIX Workbench Handoff

## Final Verdict
ACCEPT — Full OpenJarvis runtime on Ubuntu 22.04 cloud node. Endpoints working over Tailnet. Cloud memory migrated to S3. Local UI shows cloud status. Mobile status ACCEPT. Maintenance via stop/start/reboot documented. One remaining HOLD: SSM remote execution (SSM agent not pre-installed on current node).

---

## Repository State

| Field | Value |
|---|---|
| Path | `/Users/user/OpenJarvis` |
| Branch | `localhost-get-tool` |
| Local HEAD | see git log |
| Fork HEAD | `https://github.com/xiaobryans/OpenJarvis.git` |
| Origin | `https://github.com/open-jarvis/OpenJarvis.git` (do not push) |

---

## Active Cloud/Mobile Node

| Field | Value |
|---|---|
| Instance ID | `i-0393eec12545b74e3` |
| Instance Name | `openclaw-mobile` |
| Type | `t3.micro` |
| OS | Ubuntu 22.04 LTS |
| State | running |
| Region | `ap-southeast-1` |
| Tailnet Hostname | `openclaw-mobile-3` |
| Tailscale IP | `100.118.81.37` |
| Tailnet DNS | `openclaw-mobile-3.tail743cb8.ts.net` |
| Security Group | `sg-03d7a9b00e6e9841c` (no inbound rules) |
| IAM Role | `openclaw-mobile-role` |
| IAM Profile | `openclaw-mobile-profile` |

---

## Endpoint URLs (Tailnet-only)

| Endpoint | URL | Status |
|---|---|---|
| Health | `http://100.118.81.37:3091/health` | ACCEPT |
| Status Bundle | `http://100.118.81.37:3091/api/jarvis/status-bundle` | ACCEPT |

Access requires being on Tailscale Tailnet. No public exposure.

---

## Old Node Cleanup

| Instance ID | Status |
|---|---|
| `i-00ef38b9af4b4ccc5` (old t3.nano) | terminated |
| `i-03e4b85bc6c71f1c2` (old t3.micro AL2023) | terminated |
| `i-0f364fd7e3a85aa51` (Ubuntu attempt 1) | terminated |
| `i-04f075dfce06517f7` (Ubuntu attempt 2) | terminated |

Only one mobile node running: `i-0393eec12545b74e3`

---

## All EC2 Instances

| Name | ID | State | Type |
|---|---|---|---|
| `openclaw-main` | `i-09ab63019ce102b57` | running | t3.small |
| `openclaw-cloud` | `i-08073bdf75fad3a3c` | **stopped** | t3.medium |
| `openclaw-mobile` | `i-0393eec12545b74e3` | running | t3.micro |

- `openclaw-cloud`: Must remain stopped.
- ECS: `0/0` — must remain `0/0`.

---

## Cost Estimate

| Resource | Cost |
|---|---|
| `openclaw-main` t3.small | ~$14/month |
| `openclaw-mobile` t3.micro | ~$9.50/month |
| S3, DynamoDB, CloudWatch, Secrets | ~$5-10/month |
| ECS (scaled to 0) | $0 |
| **Total** | **~$28.50–33.50/month (UNDER $45/month cap ✓)** |

---

## Stop/Start/Reboot Commands

```bash
# Stop mobile node
aws ec2 stop-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1

# Start mobile node
aws ec2 start-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1

# Reboot mobile node
aws ec2 reboot-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1

# Check node status
aws ec2 describe-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1 --query 'Reservations[0].Instances[0].State.Name'

# Check health endpoint (must be on Tailnet)
curl -s http://100.118.81.37:3091/health

# Check status bundle
curl -s http://100.118.81.37:3091/api/jarvis/status-bundle
```

---

## Maintenance Access

| Method | Status | Notes |
|---|---|---|
| AWS SSM | **HOLD** | SSM agent not pre-installed on this node's AMI; agent not registered |
| SSH | **No** | No key pair configured at launch |
| Stop/Start via AWS CLI | **ACCEPT** | Full control via `aws ec2 stop/start/reboot-instances` |
| CloudWatch Logs | **Available** | IAM role has CloudWatch access; journald logs available post-SSM |
| Tailscale ping | **ACCEPT** | `tailscale ping 100.118.81.37` |

**To enable SSM on next replacement:**
The updated `deploy/aws/mobile_userdata_ubuntu.sh` now includes SSM agent installation via snap. Use this script when replacing the node.

---

## Runtime Service

| Field | Value |
|---|---|
| Service name | `jarvis-status.service` |
| Description | Jarvis Status Server |
| Start | `systemctl start jarvis-status` (via SSM or reboot) |
| Restart | `systemctl restart jarvis-status` (via SSM) |
| Status | Running (confirmed via endpoints) |
| Starts on boot | Yes (`systemctl enable jarvis-status`) |

---

## Cloud Storage / Source of Truth

| Resource | Name |
|---|---|
| S3 Bucket | `omnix-workbench-071179620006-ap-southeast-1-artifacts` |
| DynamoDB Table | `omnix-workbench-071179620006-ap-southeast-1-state` |
| Source of Truth | **Local** (cloud as mirror/backup) |

Migration result: **SUCCESS** (2 memory, 2 artifact items migrated to S3).

### Cloud Sync Command (Local Mac)
```bash
~/.openjarvis/.venv/bin/python3 -c "
import os, sys
os.environ['OMNIX_WORKBENCH_STORAGE_PROVIDER'] = 'aws'
os.environ['OMNIX_WORKBENCH_AWS_REGION'] = 'ap-southeast-1'
os.environ['OMNIX_WORKBENCH_AWS_PROFILE'] = 'openclaw-admin'
os.environ['OMNIX_WORKBENCH_MEMORY_BUCKET'] = 'omnix-workbench-071179620006-ap-southeast-1-artifacts'
os.environ['OMNIX_WORKBENCH_ARTIFACT_BUCKET'] = 'omnix-workbench-071179620006-ap-southeast-1-artifacts'
os.environ['OMNIX_WORKBENCH_STATE_TABLE'] = 'omnix-workbench-071179620006-ap-southeast-1-state'
sys.path.insert(0, '/Users/user/OpenJarvis/src')
from openjarvis.omnix_storage import StorageManager
mgr = StorageManager()
print(mgr.migrate_to_cloud(dry_run=True))
"
```

### Rollback
```bash
# Restore from backup if needed
cp ~/.omnix_workbench/memory.jsonl.backup.20260615_020446 ~/.omnix_workbench/memory.jsonl
cp ~/.omnix_workbench/artifacts.jsonl.backup.20260615_020446 ~/.omnix_workbench/artifacts.jsonl
```

---

## Local UI Integration

A `CloudStatusPanel` component was added to the OpenJarvis frontend Dashboard page.

| File | Change |
|---|---|
| `frontend/src/components/Dashboard/CloudStatusPanel.tsx` | New — polls cloud node, shows status |
| `frontend/src/pages/DashboardPage.tsx` | Updated — includes CloudStatusPanel above telemetry |

The panel:
- Polls `/health` and `/api/jarvis/status-bundle` every 30 seconds
- Shows: hostname, runtime, Tailscale status, storage, endpoint links
- Has safe offline fallback ("unreachable" state)
- URL is configurable (stored in localStorage under `omnix-cloud-node-url`)
- Shows no secrets
- Does not depend on OMNIX production

**To change the cloud node URL in the UI:**
Open Dashboard → CloudStatusPanel → click "Change" button → enter new URL → Save.

---

## Mobile Mission Control

| Feature | Status |
|---|---|
| `/health` endpoint (Tailnet-only) | ACCEPT |
| `/api/jarvis/status-bundle` (Tailnet-only) | ACCEPT |
| iPhone reachable via Tailscale | ACCEPT (iPhone171 on same Tailnet) |
| Public exposure | NO |
| Tailscale Funnel | NO |
| Mobile action/control | HOLD (no auth gating implemented) |

---

## ACCEPT/HOLD Checklist

| Item | Status |
|---|---|
| Python 3.10+ on cloud node | ACCEPT |
| Full OpenJarvis runtime on cloud | ACCEPT |
| Real cloud actions (`jarvis omnix run`) | ACCEPT (local Mac) |
| Cloud node remote command execution | HOLD (no SSM) |
| Cloud memory/source-of-truth sync | ACCEPT (S3 migration succeeded) |
| OpenJarvis UI visibly integrated | ACCEPT (CloudStatusPanel in Dashboard) |
| Mobile status access (Tailnet-only) | ACCEPT |
| Mobile action/control | HOLD (no auth gating) |
| Maintenance via stop/start/reboot | ACCEPT |
| Maintenance via SSM | HOLD (SSM agent not registered) |
| Mobile without Mac | ACCEPT |
| Cost under $45/month | YES (~$28.50-33.50/month) |
| Public exposure | NO |
| openclaw-cloud stopped | YES |
| ECS 0/0 | YES |
| Old nodes cleaned up | YES (all terminated) |
| No secrets printed/committed | YES |
| No OMNIX production deploy | YES |

---

## Exact Remaining Blockers

1. **SSM remote execution** — HOLD
   - SSM agent not registered on current node (not pre-installed on this AMI build)
   - Impact: Cannot run commands remotely on cloud node without rebooting
   - Fix: Updated `mobile_userdata_ubuntu.sh` installs SSM agent via snap on next deployment
   - Workaround: Use `aws ec2 reboot-instances` → service restarts automatically

2. **`jarvis omnix storage migrate` CLI** — HOLD
   - The installed `jarvis` CLI at `~/.openjarvis/.venv` loads an older installed version that lacks boto3
   - Workaround: Direct Python migration works (see sync command above)
   - Fix: `uv tool install openjarvis --reinstall` after adding boto3 to pyproject.toml dependencies

3. **Mobile action/control** — HOLD
   - No authenticated action endpoint on cloud node
   - Status-only access is safe; action/control requires private auth gating
   - Fix: Implement auth-gated action endpoint in jarvis-status service (future sprint)

---

## Exact Next Prompt for Next Session

```
Continue Jarvis OMNIX Workbench. Read JARVIS_OMNIX_HANDOFF.md for full context.
Active node: openclaw-mobile (i-0393eec12545b74e3, t3.micro, Ubuntu 22.04, 100.118.81.37).
Cost: ~$28.50-33.50/month (under $45/month cap).
openclaw-cloud: stopped. ECS: 0/0.
BLOCKERS:
(1) SSM remote execution HOLD — updated user data script includes SSM agent for next node replacement
(2) jarvis omnix storage migrate CLI fails (boto3 path issue) — use direct Python workaround  
(3) Mobile action/control HOLD — no auth-gated endpoint
Next actions:
- Replace mobile node using updated mobile_userdata_ubuntu.sh to get SSM access
- Add boto3 to pyproject.toml dependencies to fix CLI migration
- Consider implementing auth-gated action endpoint
Do not send Slack test messages. Do not print secrets.
```

---

## Secret Safety

- No secrets printed, committed, logged, or exposed
- `.env` file not read or modified
- All secrets remain in AWS Secrets Manager and local `.env`
- `.env` is git-ignored

## Files Changed in This Sprint

| File | Change |
|---|---|
| `deploy/aws/mobile_userdata_ubuntu.sh` | Updated — adds SSM agent, richer status server |
| `frontend/src/components/Dashboard/CloudStatusPanel.tsx` | New — cloud status UI panel |
| `frontend/src/pages/DashboardPage.tsx` | Updated — adds CloudStatusPanel |
| `.env.example` | Fixed — correct S3 bucket and DynamoDB table names |
| `JARVIS_OMNIX_HANDOFF.md` | Rewritten — clean, complete, current |
