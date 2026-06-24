# Fargate Worker Deployment Contract

**Status:** CODE_READY — not deployed  
**Blocker:** B6 — live ECS Fargate service not started  
**Last updated:** 2026-06-24 (Plan 2 Fargate Worker Readiness Sprint)

This document specifies the deployment contract for the OpenJarvis Fargate cloud worker.  
It contains no secret values, no token values, no bucket names, no account IDs, and no OAuth paths.

---

## Purpose

The Fargate worker enables MacBook-off parity by running the OpenJarvis runtime in AWS ECS Fargate.
Once deployed, it closes or partially closes:

| Blocker | How it is closed |
|---------|-----------------|
| B2 | GitHub/Slack/Telegram tokens injected at Fargate task level → connectors available cloud-side |
| B5C | Worker consumes `NotificationQueue.list_pending()` and routes to external provider adapters |
| B6 | Worker process is running in ECS Fargate → MacBook-off execution becomes possible |
| B8 | Worker executes workspace sync to S3 on startup and/or on schedule |

---

## Runtime Roles

### ECS Task Execution Role
- Pull container image from ECR
- Read secrets from AWS Secrets Manager
- Write logs to CloudWatch

### ECS Task Role (runtime)
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on artifact bucket
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`, `dynamodb:Scan` on state table
- `secretsmanager:GetSecretValue` on the project secrets resource

All permissions are in `deploy/aws/main.tf`.

---

## Required Environment Variable Names (no values)

These must be injected at ECS task level. Values must come from AWS Secrets Manager or
ECS task environment — never from source code or committed files.

| Variable Name | Purpose | Sensitivity |
|---------------|---------|-------------|
| `PORT` | Worker HTTP port (default: 3091) | Low |
| `HOST` | Bind address (default: 0.0.0.0) | Low |
| `OMNIX_WORKBENCH_AWS_REGION` | AWS region | Low |
| `OMNIX_WORKBENCH_STORAGE_PROVIDER` | Must be "aws" | Low |
| `OMNIX_WORKBENCH_MEMORY_BUCKET` | S3 bucket for memory/state | Medium |
| `OMNIX_WORKBENCH_ARTIFACT_BUCKET` | S3 bucket for artifacts | Medium |
| `OMNIX_WORKBENCH_STATE_TABLE` | DynamoDB table name | Medium |
| `OPENJARVIS_API_KEY` | Bearer token for all /v1/* routes | **HIGH** |
| `GITHUB_TOKEN` | GitHub connector (env-var-based) | **HIGH** |
| `SLACK_BOT_TOKEN` | Slack connector (env-var-based) | **HIGH** |
| `TELEGRAM_BOT_TOKEN` | Telegram connector (canonical name) | **HIGH** |

All HIGH sensitivity variables must come from Secrets Manager at task startup.
Do not commit any values to source control.

---

## Secret Injection Expectations

- Secrets Manager ARN is defined in `deploy/aws/main.tf`
- The ECS task definition (also in `main.tf`) references secrets via `valueFrom` pointing to Secrets Manager
- IAM policy allows the task execution role to call `secretsmanager:GetSecretValue`
- Worker starts up and reads from env; never reads `.env` files or hardcoded paths at runtime

---

## Required Capabilities (presence-only — no values)

| Capability | Type | Required for |
|------------|------|-------------|
| S3 artifact bucket | AWS resource | Workspace sync (B8), memory sync |
| S3 memory bucket | AWS resource | Memory cloud sync |
| DynamoDB state table | AWS resource | State persistence |
| Secrets Manager secret | AWS resource | Token injection |
| CloudWatch log group | AWS resource | Observability |

---

## Worker Startup Behaviour

1. Read env vars from task environment (injected via Secrets Manager + plain env)
2. Validate required vars are non-empty (log ERROR if missing — do not crash silently)
3. Start HTTP server on `PORT` (default 3091)
4. Register health endpoint `GET /health` (public, no auth)
5. Validate S3 bucket reachability (lightweight `head_bucket` call)
6. Begin notification queue consumer loop (reads `NotificationQueue.list_pending()`)
7. Begin workspace sync on startup if S3 config is present

---

## Health Check Behaviour

- `GET /health` — always public, always returns `{"status": "ok"}` if process is alive
- ECS service health check: HTTP `GET /health` on port 3091, 30s interval, 3 retries
- `GET /v1/system/health` — auth-gated, returns S3 status, GitHub token presence (presence-only)
- **Never** expose token values, bucket names, or account IDs in health responses

---

## Notification Delivery Behaviour (B5C)

Once deployed, the worker implements the B5C consumer:

1. On a configurable interval, call `NotificationQueue.list_pending()`
2. For each pending event, dispatch via `NotificationDispatcher` with configured provider adapters
3. If delivery succeeds, call `NotificationQueue.mark_delivery_status(event_id, STATUS_SENT)`
4. If delivery fails, retry up to N times; then mark `STATUS_FAILED`
5. Never approve or deny approval requests — only send notification

Provider adapters (Slack, Telegram) receive only safe metadata:
- `event_id` — opaque UUID prefix
- `action_type` — safe action description
- `risk_level` — "low" | "medium" | "high" | "critical"
- `message` — human-readable notification text

---

## Workspace Sync Behaviour (B8)

Once deployed:

1. On startup, compare local git index (from S3 state snapshot) with current state
2. Push any new git-tracked file metadata to S3 artifact bucket
3. On schedule (configurable interval), re-sync any changed files
4. Never sync `.env` files, private keys, OAuth token files, or credential files
5. Report sync status via `GET /v1/files/workspace/status` (auth-gated)

---

## Long-Running Task Execution (B6)

Once deployed:

1. Poll long-running task queue for pending tasks
2. Execute approved tasks within worker process
3. Write results to S3 state store
4. Approval gate is enforced: tier 2+ tasks require prior approval before execution
5. Report task status via `GET /v1/tasks` (auth-gated)

---

## Failure Modes

| Mode | Meaning | Action |
|------|---------|--------|
| `NOT_CONFIGURED` | Required env vars absent | Check ECS task definition; do not start worker |
| `CONFIGURED_NOT_DEPLOYED` | Env vars OK; ECS service not running | Run `terraform apply` or start ECS service |
| `DEPLOYED_NOT_REACHABLE` | ECS task running but health check fails | Check security group, NAT gateway, port mapping |
| `PARTIAL` | Some capabilities available; some missing | Check individual env var injection and Secrets Manager |
| `BLOCKED` | Deployment infrastructure issue | Check VPC, subnet, IAM roles |
| `READY` | All layers confirmed; health check responding | MacBook-off parity active |

---

## Terraform Infrastructure

All IaC is in `deploy/aws/main.tf`:

- VPC + private subnets (no public IP on worker)
- NAT Gateway for outbound-only access
- ECS Cluster + Fargate task definition
- S3 bucket (versioned, AES256 encrypted)
- DynamoDB table (pay-per-request)
- Secrets Manager secret
- CloudWatch log group (7-day retention)
- Security group: inbound port 3091 from VPC only; outbound unrestricted

---

## Deployment Steps (for Bryan or authorized sprint)

1. Set required secret values in AWS Secrets Manager (HIGH sensitivity vars)
2. Build and push Docker image to ECR (use `deploy/aws/Dockerfile`)
3. Run `terraform plan` in `deploy/aws/` — verify no unexpected resources
4. Run `terraform apply` — creates ECS service and starts Fargate task
5. Verify: `curl http://<task-ip>:3091/health` returns `{"status": "ok"}`
6. Verify: `curl -H "Authorization: Bearer $OPENJARVIS_API_KEY" http://<task-ip>:3091/v1/system/health`
7. Update `PLAN2_AUTONOMOUS_SESSION_STATE.md` with deployed URL and health proof
8. Close B6 in blocker registry

**Note:** Steps 1–8 require live AWS credentials and are authorized only as a separate
live-deployment sprint. This document only defines the contract; it does not execute deployment.

---

## What This Sprint Does NOT Do

- Does not deploy live AWS/Fargate resources
- Does not read or print secret values
- Does not perform live S3 or DynamoDB calls
- Does not modify existing approval gates
- Does not claim B6 closed (B6 remains open until live deployment is verified)
- Does not require Tauri rebuild
