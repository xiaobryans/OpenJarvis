# AWS Cloud Deployment Preparation

## Overview

This directory contains AWS cloud deployment preparation files for Jarvis OMNIX Workbench v1. These files are templates and documentation only - **do not apply without explicit approval**.

## Architecture

### Compute: ECS Fargate (Preferred)

**Choice Justification:**
- Managed compute, no EC2 instance management
- Auto-scaling capabilities
- Pay-per-use model
- Integrated with other AWS services
- No patching overhead

**Alternative: EC2**
- More control over underlying infrastructure
- Fixed cost predictable
- Higher operational overhead
- Requires patching and maintenance

### Storage: S3 for Artifacts, DynamoDB for State

**Choice Justification:**
- **S3**: Object storage ideal for artifacts (documents, reports, files)
- **DynamoDB**: NoSQL database for state/metadata with low latency
- Both services have free tier for testing
- Integrated with ECS and Lambda
- Cost-effective for read-heavy workloads

**Alternative: S3 for both**
- Simpler architecture
- Lower latency for simple JSONL files
- No database management overhead
- May have higher cost at scale

### Secrets: AWS Secrets Manager

**Choice Justification:**
- Secure secret storage with encryption
- Automatic rotation support
- IAM-based access control
- Audit logging
- Integrated with ECS

**Alternative: SSM Parameter Store**
- Lower cost
- Simpler for small deployments
- No automatic rotation
- Less audit capability

## Required Resources

### Compute
- **ECS Cluster**: `omnix-workbench-cluster`
- **ECS Task Definition**: `omnix-workbench-task`
- **ECS Service**: `omnix-workbench-service`
- **Fargate Capacity**: 0.5 vCPU, 1-2 GB RAM minimum

### Storage
- **S3 Bucket**: `omnix-workbench-artifacts-{account-id}-{region}`
- **DynamoDB Table**: `omnix-workbench-state`
- **DynamoDB Capacity**: On-demand (pay per request)

### Networking
- **VPC**: `omnix-workbench-vpc`
- **Subnets**: 2 private subnets
- **Security Groups**: Private-only, no public access
- **Load Balancer**: Application LB for internal access only

### Secrets
- **Secret**: `omnix-workbench/secrets`
- **Keys**: Slack token, database credentials, API keys

### Monitoring
- **CloudWatch Logs**: `/aws/ecs/omnix-workbench`
- **CloudWatch Alarms**: CPU, memory, error rates
- **Health Check**: HTTP endpoint `/health`

## IAM Permissions Required

### ECS Execution Role
- `ecs:ExecuteCommand`
- `ecs:RunTask`
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `s3:GetObject`, `s3:PutObject` (for artifacts bucket)
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` (for state table)
- `secretsmanager:GetSecretValue` (for secrets)

### Task Role
- `s3:GetObject`, `s3:PutObject` (for artifacts bucket)
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` (for state table)
- `secretsmanager:GetSecretValue` (for secrets)

## Required Environment Variables

### Storage Configuration
- `OMNIX_WORKBENCH_STORAGE_PROVIDER=aws`
- `OMNIX_WORKBENCH_SOURCE_OF_TRUTH=cloud`
- `OMNIX_WORKBENCH_AWS_REGION=ap-southeast-1`
- `OMNIX_WORKBENCH_AWS_PROFILE=openclaw-admin`
- `OMNIX_WORKBENCH_MEMORY_BUCKET=omnix-workbench-artifacts-{account-id}-{region}`
- `OMNIX_WORKBENCH_ARTIFACT_BUCKET=omnix-workbench-artifacts-{account-id}-{region}`
- `OMNIX_WORKBENCH_STATE_TABLE=omnix-workbench-state`

### Mission Control Configuration
- `OPENCLAW_WORKSPACE_DIR=/app/openclaw-workspace`
- `PORT=3091`
- `HOST=0.0.0.0` (internal VPC only, not public)

### AWS Configuration
- `AWS_REGION=ap-southeast-1`
- `AWS_DEFAULT_REGION=ap-southeast-1`

## Cost Estimates

### Minimum Monthly Cost (t2.micro equivalent)
- **ECS Fargate**: $15-30/month (0.5 vCPU, 1 GB RAM, 24/7)
- **S3 Storage**: $0.023/GB/month (assuming 1-10 GB)
- **DynamoDB**: $1-5/month (on-demand, low traffic)
- **CloudWatch Logs**: $0.50-2/month
- **Data Transfer**: $0-5/month (internal VPC only)
- **Secrets Manager**: $0.40/month per secret
- **Total**: $20-45/month minimum

### Production Monthly Cost (m5.large equivalent)
- **ECS Fargate**: $100-200/month (2 vCPU, 4 GB RAM, 24/7)
- **S3 Storage**: $0.23-2.30/month (10-100 GB)
- **DynamoDB**: $10-50/month (provisioned capacity)
- **CloudWatch Logs**: $5-10/month
- **Data Transfer**: $10-20/month
- **Secrets Manager**: $0.40/month per secret
- **Total**: $130-290/month

## Security Model

### Access Control
- **VPC**: Private subnets only, no public internet gateway
- **Security Groups**: Restrictive, allow only required traffic
- **IAM**: Least privilege, role-based access
- **Secrets**: Encrypted at rest and in transit
- **Audit**: CloudTrail enabled for API calls

### Admin Access
- **Bastion Host**: Jump box for admin access
- **VPN**: VPN or AWS Client VPN for remote admin
- **MFA**: Required for IAM users with admin access
- **Session Manager**: For secure shell access to containers

## Health Checks

### HTTP Health Endpoint
- **Path**: `/health`
- **Method**: GET
- **Response**: JSON with status, timestamp, dependencies
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Unhealthy Threshold**: 3 consecutive failures

### Dependencies Check
- Mission Control bridge health
- OpenClaw workspace accessibility
- AWS services connectivity
- Storage bucket access

## Rollback Procedure

### Manual Rollback
1. Deploy previous ECS task definition
2. Update ECS service to use previous task definition
3. Monitor CloudWatch logs for errors
4. Verify health checks pass
5. Validate Mission Control endpoint

### Automated Rollback (if implemented)
- ECS deployment rollback on health check failure
- Auto Scaling Group rollback on alarm trigger
- CloudFormation stack rollback on deployment failure

## Destroy/Cleanup

### Manual Cleanup
1. Delete ECS service: `aws ecs delete-service --cluster omnix-workbench-cluster --service omnix-workbench-service`
2. Delete task definitions: `aws ecs deregister-task-definition --task-definition omnix-workbench-task`
3. Delete S3 bucket: `aws s3 rb s3://omnix-workbench-artifacts-{account-id}-{region} --force`
4. Delete DynamoDB table: `aws dynamodb delete-table --table-name omnix-workbench-state`
5. Delete CloudWatch log groups: `aws logs delete-log-group --log-group-name /aws/ecs/omnix-workbench`
6. Delete secrets: `aws secretsmanager delete-secret --secret-id omnix-workbench/secrets`
7. Delete VPC and networking resources

### Automated Cleanup (Terraform)
```bash
terraform destroy -auto-approve
```

## Approval Checklist

Before deploying, ensure:

- [ ] Bryan has approved budget ($20-45/month minimum)
- [ ] Bryan has approved architecture (ECS Fargate, S3, DynamoDB)
- [ ] AWS account/region confirmed (071179620006, ap-southeast-1)
- [ ] IAM permissions verified (openclaw-admin profile)
- [ ] Security model reviewed and approved
- [ ] Rollback procedure documented and tested
- [ ] Monitoring and alerting configured
- [ ] Backup strategy defined
- [ ] Compliance requirements reviewed
- [ ] Team trained on operations and maintenance

## Next Steps

1. Review this architecture with Bryan
2. Obtain explicit approval and budget authorization
3. Create Terraform or CloudFormation templates in this directory
4. Run `terraform plan` or `cloudformation package` to preview changes
5. Obtain final approval before running `terraform apply` or `cloudformation deploy`
6. Deploy and validate
7. Configure monitoring and alerting
8. Document operational procedures

## Important Notes

- **Do not deploy without explicit approval**
- **Do not create paid resources without budget authorization**
- **Do not expose services publicly**
- **Do not modify production OMNIX infrastructure**
- **Always test in development environment first**
- **Always have rollback plan ready**
