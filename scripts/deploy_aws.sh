#!/usr/bin/env bash
set -euo pipefail

export PATH="/Users/yq225/.local/bin:/Users/yq225/Library/Python/3.9/bin:$PATH"

STACK_NAME="${STACK_NAME:-aussie-ecolens}"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
APP_URL="${APP_URL:-http://127.0.0.1:8080/}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"
TAGGER_MODE="${TAGGER_MODE:-filename}"
GCP_MIRROR_ENDPOINT="${GCP_MIRROR_ENDPOINT:-}"
GCP_SHARED_SECRET="${GCP_SHARED_SECRET:-}"
MODEL_INFERENCE_ENDPOINT="${MODEL_INFERENCE_ENDPOINT:-}"
MODEL_SHARED_SECRET="${MODEL_SHARED_SECRET:-}"
FFMPEG_LAYER_ARN="${FFMPEG_LAYER_ARN:-}"

sam build --template-file infra/aws/template.yaml

PARAM_OVERRIDES=(
  ProjectName="$STACK_NAME"
  AppCallbackUrl="$APP_URL"
  AppLogoutUrl="$APP_URL"
  TaggerMode="$TAGGER_MODE"
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
