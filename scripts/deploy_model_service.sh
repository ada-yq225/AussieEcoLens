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
CLASSIFIER_BLOB="${CLASSIFIER_BLOB:-course-model/model.pt}"
DETECTOR_BLOB="${DETECTOR_BLOB:-course-model/mdv5a.pt}"
DETECTION_THRESHOLD="${DETECTION_THRESHOLD:-0.05}"
PREDICTION_THRESHOLD="${PREDICTION_THRESHOLD:-0.0}"

gcloud config set project "$GCP_PROJECT_ID"
gcloud storage buckets create "gs://$MODEL_BUCKET" --location="$GCP_REGION" || true
if ! gcloud storage ls "gs://$MODEL_BUCKET/$CLASSIFIER_BLOB" >/dev/null 2>&1; then
  gcloud storage cp "$MODEL_SOURCE_DIR/model.pt" "gs://$MODEL_BUCKET/$CLASSIFIER_BLOB"
fi
if ! gcloud storage ls "gs://$MODEL_BUCKET/$DETECTOR_BLOB" >/dev/null 2>&1; then
  gcloud storage cp "$MODEL_SOURCE_DIR/mdv5a.pt" "gs://$MODEL_BUCKET/$DETECTOR_BLOB"
fi

gcloud run deploy aussie-ecolens-model \
  --source=src/cloud/model_service \
  --region="$GCP_REGION" \
  --allow-unauthenticated \
  --memory=8Gi \
  --cpu=4 \
  --timeout=900 \
  --min-instances="$MODEL_MIN_INSTANCES" \
  --set-env-vars="MODEL_BUCKET=$MODEL_BUCKET,MODEL_SHARED_SECRET=$MODEL_SHARED_SECRET,CLASSIFIER_BLOB=$CLASSIFIER_BLOB,DETECTOR_BLOB=$DETECTOR_BLOB,DETECTION_THRESHOLD=$DETECTION_THRESHOLD,PREDICTION_THRESHOLD=$PREDICTION_THRESHOLD"

gcloud run services describe aussie-ecolens-model \
  --region="$GCP_REGION" \
  --format="value(status.url)"
