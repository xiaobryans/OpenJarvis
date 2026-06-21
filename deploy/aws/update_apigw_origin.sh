#!/usr/bin/env bash
# update_apigw_origin.sh — Re-register ECS task private IP in NLB target group
#                          after an ECS task restart.
#
# Architecture (post-private-closure):
#   Client → HTTPS → API Gateway → VPC Link → NLB (internal) → ECS:8000 (private IP only)
#   Direct public HTTP to ECS is blocked by security group (port 8000/3091 not open to 0.0.0.0/0).
#
# When to run:
#   After every ECS task restart (ECS Fargate assigns a new private IP on restart).
#   The NLB target group must be updated to point at the new private IP.
#   API Gateway integration URI (NLB listener ARN) does NOT change — no API Gateway update needed.
#
# Usage:
#   ./update_apigw_origin.sh [new_private_ip]
#
# Without argument: auto-discovers current ECS task private IP.

set -euo pipefail

PROFILE="${AWS_PROFILE:-openclaw-admin}"
REGION="ap-southeast-1"
CLUSTER="omnix-workbench-071179620006-ap-southeast-1-cluster"
SERVICE="omnix-workbench-jarvis-full-service"
TARGET_GROUP_ARN="arn:aws:elasticloadbalancing:ap-southeast-1:071179620006:targetgroup/jarvis-full-tg/9e7c0e318a81ce4b"
ECS_PORT="8000"

# --- Discover new private IP ---
if [[ $# -ge 1 ]]; then
  NEW_PRIVATE_IP="$1"
else
  echo "Discovering current ECS task private IP..."
  TASK_ARN=$(aws ecs list-tasks \
    --cluster "$CLUSTER" --service-name "$SERVICE" \
    --profile "$PROFILE" --region "$REGION" \
    --query 'taskArns[0]' --output text 2>/dev/null)

  if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
    echo "ERROR: No running task found for service $SERVICE"
    exit 1
  fi

  NEW_PRIVATE_IP=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" --tasks "$TASK_ARN" \
    --profile "$PROFILE" --region "$REGION" \
    --query 'tasks[0].attachments[0].details[?name==`privateIPv4Address`].value' \
    --output text 2>/dev/null)
  echo "Discovered private IP: $NEW_PRIVATE_IP"
fi

# --- Deregister all old targets ---
OLD_TARGETS=$(aws elbv2 describe-target-health \
  --target-group-arn "$TARGET_GROUP_ARN" \
  --profile "$PROFILE" --region "$REGION" \
  --query 'TargetHealthDescriptions[*].[Target.Id,Target.Port]' \
  --output text 2>/dev/null)

if [[ -n "$OLD_TARGETS" ]]; then
  while IFS=$'\t' read -r OLD_IP OLD_PORT; do
    if [[ -n "$OLD_IP" ]]; then
      echo "Deregistering old target: $OLD_IP:$OLD_PORT"
      aws elbv2 deregister-targets \
        --target-group-arn "$TARGET_GROUP_ARN" \
        --targets "Id=${OLD_IP},Port=${OLD_PORT}" \
        --profile "$PROFILE" --region "$REGION" > /dev/null
    fi
  done <<< "$OLD_TARGETS"
fi

# --- Register new private IP ---
echo "Registering new target: $NEW_PRIVATE_IP:$ECS_PORT"
aws elbv2 register-targets \
  --target-group-arn "$TARGET_GROUP_ARN" \
  --targets "Id=${NEW_PRIVATE_IP},Port=${ECS_PORT}" \
  --profile "$PROFILE" --region "$REGION"

echo ""
echo "NLB target updated → $NEW_PRIVATE_IP:$ECS_PORT"
echo "API Gateway VPC Link integration unchanged (NLB listener ARN is stable)."
echo ""
echo "Test (HTTPS — API Gateway only path):"
echo "  curl -s https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com/health"
echo ""
echo "Allow ~30s for NLB health check to pass after registering new target."
