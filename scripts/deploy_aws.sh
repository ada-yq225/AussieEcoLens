#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-aussie-ecolens}"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
APP_URL="${APP_URL:-http://127.0.0.1:8080/}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"
TAGGER_MODE="${TAGGER_MODE:-filename}"
GCP_MIRROR_ENDPOINT="${GCP_MIRROR_ENDPOINT:-}"
GCP_SHARED_SECRET="${GCP_SHARED_SECRET:-}"
FFMPEG_LAYER_ARN="${FFMPEG_LAYER_ARN:-}"

sam build --template-file infra/aws/template.yaml
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides \
    ProjectName="$STACK_NAME" \
    AppCallbackUrl="$APP_URL" \
    AppLogoutUrl="$APP_URL" \
    NotificationEmail="$NOTIFICATION_EMAIL" \
    TaggerMode="$TAGGER_MODE" \
    GcpMirrorEndpoint="$GCP_MIRROR_ENDPOINT" \
    GcpSharedSecret="$GCP_SHARED_SECRET" \
    FFmpegLayerArn="$FFMPEG_LAYER_ARN"

API_URL="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)"
COGNITO_DOMAIN="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='CognitoDomain'].OutputValue" --output text)"
CLIENT_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)"

python3 scripts/render_web_config.py cloud "$API_URL" "$COGNITO_DOMAIN" "$CLIENT_ID" "$APP_URL" "$APP_URL"

echo "AWS deployed."
echo "API_URL=$API_URL"
echo "COGNITO_DOMAIN=$COGNITO_DOMAIN"
echo "CLIENT_ID=$CLIENT_ID"
echo "web/config.js updated for cloud mode."
