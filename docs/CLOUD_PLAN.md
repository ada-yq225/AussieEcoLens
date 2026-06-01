# Cloud Deployment Plan

This document marks every step that needs a real cloud account.

## Implemented Target Architecture

- AWS Cognito: user registration, email verification, sign-in, tokens.
- AWS S3: primary media upload bucket and thumbnail bucket.
- AWS Lambda: upload processor, query processor, tag editor, deleter, notification dispatcher.
- AWS API Gateway: REST API protected by Cognito authorizer.
- AWS DynamoDB: media metadata and tag index.
- AWS SNS: email notification topics/subscriptions.
- GCP Cloud Storage: secondary metadata mirror bucket.
- GCP Cloud Functions gen2: receives signed mirror requests from AWS Lambda.

## Manual Login Required

1. AWS console login.
2. Confirm AWS region and AWS Academy limitations.
3. Create or confirm Cognito user pool.
4. Create S3 buckets.
5. Create DynamoDB tables.
6. Create Lambda execution roles and API Gateway authorizer.
7. Confirm SNS email subscription.
8. GCP console login.
9. Create GCP project, enable Cloud Functions/Run and Cloud Storage.
10. Create service account for cross-cloud calls.
11. Deploy `scripts/deploy_gcp.sh`, then deploy AWS with the printed GCP endpoint.

## Secrets and Environment Variables

The real cloud deployment must not commit secrets. Expected local environment values:

```text
AWS_REGION=
COGNITO_USER_POOL_ID=
COGNITO_CLIENT_ID=
MEDIA_BUCKET=
THUMBNAIL_BUCKET=
DYNAMODB_TABLE=
SNS_TOPIC_ARN=
GCP_PROJECT_ID=
GCP_BUCKET=
GCP_SERVICE_ACCOUNT_JSON=
```

## Cost Controls

- Use small test images and very short videos.
- Configure AWS Budget alerts before deployment.
- Set Lambda timeouts.
- Delete test buckets and database records after demo.
- Avoid always-on VMs.
