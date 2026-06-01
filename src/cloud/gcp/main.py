from __future__ import annotations

import json
import os
import time

from google.cloud import storage


BUCKET_NAME = os.environ["GCP_BUCKET"]
SHARED_SECRET = os.environ.get("GCP_SHARED_SECRET", "")
storage_client = storage.Client()


def mirror_media(request):
    """Mirror AWS media metadata into GCP Cloud Storage.

    AWS Lambda sends a signed JSON payload after each successful upload. This
    gives the project a real second-cloud workflow while keeping the media files
    private in AWS S3 for the demo.
    """
    if SHARED_SECRET:
        supplied = request.headers.get("x-aussie-ecolens-secret", "")
        if supplied != SHARED_SECRET:
            return (json.dumps({"error": "unauthorised"}), 401, {"content-type": "application/json"})

    payload = request.get_json(silent=True) or {}
    checksum = payload.get("checksum")
    if not checksum:
        return (json.dumps({"error": "checksum is required"}), 400, {"content-type": "application/json"})

    payload["mirrored_at"] = time.time()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"media-metadata/{checksum}.json")
    blob.upload_from_string(json.dumps(payload, indent=2, sort_keys=True), content_type="application/json")
    return (
        json.dumps({"ok": True, "gcp_object": f"gs://{BUCKET_NAME}/{blob.name}"}),
        200,
        {"content-type": "application/json"},
    )

