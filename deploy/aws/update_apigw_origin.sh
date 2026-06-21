#!/usr/bin/env bash
# update_apigw_origin.sh — Update API Gateway HTTP API origin when ECS task IP changes.
#
# Run this after an ECS task restart to re-point the HTTPS API Gateway
# to the new ECS task public IP.
#
# Usage:
#   ./update_apigw_origin.sh [new_ip]
#
# Without argument: auto-discovers current ECS task IP.

set -euo pipefail

PROFILE="${AWS_PROFILE:-openclaw-admin}"
REGION="ap-southeast-1"
API_ID="2r8dnzlz1h"
API_PORT="8000"
CLUSTER="omnix-workbench-071179620006-ap-southeast-1-cluster"
SERVICE="omnix-workbench-jarvis-full-service"

if [[ $# -ge 1 ]]; then
  NEW_IP="$1"
else
  echo "Discovering current ECS task IP..."
  TASK_ARN=$(aws ecs list-tasks \
    --cluster "$CLUSTER" --service-name "$SERVICE" \
    --profile "$PROFILE" --region "$REGION" \
    --query 'taskArns[0]' --output text 2>/dev/null)
  ENI=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" --tasks "$TASK_ARN" \
    --profile "$PROFILE" --region "$REGION" \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
    --output text 2>/dev/null)
  NEW_IP=$(aws ec2 describe-network-interfaces \
    --network-interface-ids "$ENI" \
    --profile "$PROFILE" --region "$REGION" \
    --query 'NetworkInterfaces[0].Association.PublicIp' \
    --output text 2>/dev/null)
  echo "Discovered IP: $NEW_IP"
fi

NEW_PROXY_URI="http://${NEW_IP}:${API_PORT}/{proxy}"
NEW_ROOT_URI="http://${NEW_IP}:${API_PORT}/"

echo "Updating API Gateway $API_ID integrations to $NEW_IP..."

# Get integration IDs
INT_IDS=$(aws apigatewayv2 get-integrations \
  --api-id "$API_ID" \
  --profile "$PROFILE" --region "$REGION" \
  --query 'Items[*].[IntegrationId,IntegrationUri]' \
  --output text 2>/dev/null)

while IFS=$'\t' read -r INT_ID INT_URI; do
  if [[ "$INT_URI" == *"/{proxy}"* ]]; then
    aws apigatewayv2 update-integration \
      --api-id "$API_ID" --integration-id "$INT_ID" \
      --integration-uri "$NEW_PROXY_URI" \
      --profile "$PROFILE" --region "$REGION" > /dev/null
    echo "  Updated proxy integration $INT_ID → $NEW_PROXY_URI"
  elif [[ "$INT_URI" == *"/"* ]]; then
    aws apigatewayv2 update-integration \
      --api-id "$API_ID" --integration-id "$INT_ID" \
      --integration-uri "$NEW_ROOT_URI" \
      --profile "$PROFILE" --region "$REGION" > /dev/null
    echo "  Updated root integration $INT_ID → $NEW_ROOT_URI"
  fi
done <<< "$INT_IDS"

echo ""
echo "Done. HTTPS endpoint: https://${API_ID}.execute-api.${REGION}.amazonaws.com"
echo "Test: curl -sf https://${API_ID}.execute-api.${REGION}.amazonaws.com/health | python3 -m json.tool"
