#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="$PROJECT_DIR/tools/google-cloud-sdk/bin:$PATH"

GCP_PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-australia-southeast1}"
GCP_BUCKET="${GCP_BUCKET:?Set GCP_BUCKET}"
GCP_SHARED_SECRET="${GCP_SHARED_SECRET:?Set GCP_SHARED_SECRET}"

gcloud config set project "$GCP_PROJECT_ID"
gcloud storage buckets create "gs://$GCP_BUCKET" --location="$GCP_REGION" || true
gcloud functions deploy aussie-ecolens-mirror \
  --gen2 \
  --runtime=python311 \
  --region="$GCP_REGION" \
  --source=src/cloud/gcp \
  --entry-point=mirror_media \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="GCP_BUCKET=$GCP_BUCKET,GCP_SHARED_SECRET=$GCP_SHARED_SECRET"

gcloud functions describe aussie-ecolens-mirror \
  --gen2 \
  --region="$GCP_REGION" \
  --format="value(serviceConfig.uri)"
