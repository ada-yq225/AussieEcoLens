#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/Library/Python/3.9/bin:$PATH"

STACK_NAME="${STACK_NAME:-aussie-ecolens}"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
APP_URL="${APP_URL:-http://127.0.0.1:8080/}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"
TAGGER_MODE="${TAGGER_MODE:-filename}"
GCP_MIRROR_ENDPOINT="${GCP_MIRROR_ENDPOINT:-}"
GCP_SHARED_SECRET="${GCP_SHARED_SECRET:-}"
MODEL_INFERENCE_ENDPOINT="${MODEL_INFERENCE_ENDPOINT:-}"
MODEL_SHARED_SECRET="${MODEL_SHARED_SECRET:-}"
EMAIL_NOTIFICATION_MODE="${EMAIL_NOTIFICATION_MODE:-sns}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USERNAME="${SMTP_USERNAME:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SMTP_FROM="${SMTP_FROM:-}"
SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
FFMPEG_LAYER_ARN="${FFMPEG_LAYER_ARN:-}"

SMTP_PASSWORD="$(printf '%s' "$SMTP_PASSWORD" | tr -d '[:space:]')"

sam build --template-file infra/aws/template.yaml

PARAM_OVERRIDES=(
  ProjectName="$STACK_NAME"
  AppCallbackUrl="$APP_URL"
  AppLogoutUrl="$APP_URL"
  TaggerMode="$TAGGER_MODE"
  EmailNotificationMode="$EMAIL_NOTIFICATION_MODE"
  SmtpPort="$SMTP_PORT"
  SmtpStartTls="$SMTP_STARTTLS"
)

if [[ -n "$NOTIFICATION_EMAIL" ]]; then
  PARAM_OVERRIDES+=(NotificationEmail="$NOTIFICATION_EMAIL")
fi
if [[ -n "$GCP_MIRROR_ENDPOINT" ]]; then
  PARAM_OVERRIDES+=(GcpMirrorEndpoint="$GCP_MIRROR_ENDPOINT")
fi
if [[ -n "$GCP_SHARED_SECRET" ]]; then
  PARAM_OVERRIDES+=(GcpSharedSecret="$GCP_SHARED_SECRET")
fi
if [[ -n "$MODEL_INFERENCE_ENDPOINT" ]]; then
  PARAM_OVERRIDES+=(ModelInferenceEndpoint="$MODEL_INFERENCE_ENDPOINT")
fi
if [[ -n "$MODEL_SHARED_SECRET" ]]; then
  PARAM_OVERRIDES+=(ModelSharedSecret="$MODEL_SHARED_SECRET")
fi
if [[ -n "$SMTP_HOST" ]]; then
  PARAM_OVERRIDES+=(SmtpHost="$SMTP_HOST")
fi
if [[ -n "$SMTP_USERNAME" ]]; then
  PARAM_OVERRIDES+=(SmtpUsername="$SMTP_USERNAME")
fi
if [[ -n "$SMTP_PASSWORD" ]]; then
  PARAM_OVERRIDES+=(SmtpPassword="$SMTP_PASSWORD")
fi
if [[ -n "$SMTP_FROM" ]]; then
  PARAM_OVERRIDES+=(SmtpFrom="$SMTP_FROM")
fi
if [[ -n "$FFMPEG_LAYER_ARN" ]]; then
  PARAM_OVERRIDES+=(FFmpegLayerArn="$FFMPEG_LAYER_ARN")
fi

sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides "${PARAM_OVERRIDES[@]}"

API_URL="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)"
COGNITO_DOMAIN="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='CognitoDomain'].OutputValue" --output text)"
CLIENT_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)"

python3 scripts/render_web_config.py cloud "$API_URL" "$COGNITO_DOMAIN" "$CLIENT_ID" "$APP_URL" "$APP_URL"

echo "AWS deployed."
echo "API_URL=$API_URL"
echo "COGNITO_DOMAIN=$COGNITO_DOMAIN"
echo "CLIENT_ID=$CLIENT_ID"
echo "web/config.js updated for cloud mode."
