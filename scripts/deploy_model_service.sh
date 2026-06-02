#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="$PROJECT_DIR/tools/google-cloud-sdk/bin:$PATH"

GCP_PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-australia-southeast1}"
MODEL_BUCKET="${MODEL_BUCKET:?Set MODEL_BUCKET}"
MODEL_SHARED_SECRET="${MODEL_SHARED_SECRET:?Set MODEL_SHARED_SECRET}"
MODEL_SOURCE_DIR="${MODEL_SOURCE_DIR:-/Users/yq225/Downloads/作业资料/AussieEcoLense}"
MODEL_MIN_INSTANCES="${MODEL_MIN_INSTANCES:-0}"

gcloud config set project "$GCP_PROJECT_ID"
gcloud storage buckets create "gs://$MODEL_BUCKET" --location="$GCP_REGION" || true
if ! gcloud storage ls "gs://$MODEL_BUCKET/course-model/model.pt" >/dev/null 2>&1; then
  gcloud storage cp "$MODEL_SOURCE_DIR/model.pt" "gs://$MODEL_BUCKET/course-model/model.pt"
fi
if ! gcloud storage ls "gs://$MODEL_BUCKET/course-model/mdv5a.pt" >/dev/null 2>&1; then
  gcloud storage cp "$MODEL_SOURCE_DIR/mdv5a.pt" "gs://$MODEL_BUCKET/course-model/mdv5a.pt"
fi

gcloud run deploy aussie-ecolens-model \
  --source=src/cloud/model_service \
  --region="$GCP_REGION" \
  --allow-unauthenticated \
  --memory=8Gi \
  --cpu=4 \
  --timeout=900 \
  --min-instances="$MODEL_MIN_INSTANCES" \
  --set-env-vars="MODEL_BUCKET=$MODEL_BUCKET,MODEL_SHARED_SECRET=$MODEL_SHARED_SECRET"

gcloud run services describe aussie-ecolens-model \
  --region="$GCP_REGION" \
  --format="value(status.url)"
