# Aussie EcoLens Demo Walkthrough

This document is the working demo guide for the final assignment demonstration.

## Deployed Cloud Resources

### AWS

- Region: `ap-southeast-2`
- CloudFormation stack: `aussie-ecolens`
- API Gateway URL: `https://YOUR_API_ID.execute-api.YOUR_AWS_REGION.amazonaws.com`
- Cognito User Pool: `YOUR_COGNITO_USER_POOL_ID`
- Cognito Client ID: `YOUR_COGNITO_CLIENT_ID`
- Cognito Domain: `https://YOUR_COGNITO_DOMAIN.auth.YOUR_AWS_REGION.amazoncognito.com`
- Media S3 bucket: `YOUR_MEDIA_BUCKET`
- Thumbnail/frame S3 bucket: `YOUR_THUMBNAIL_BUCKET`
- DynamoDB table: `aussie-ecolens-metadata`
- SNS topic: `arn:aws:sns:YOUR_AWS_REGION:YOUR_AWS_ACCOUNT_ID:YOUR_SNS_TOPIC`
- ffmpeg Lambda layer: `arn:aws:lambda:YOUR_AWS_REGION:YOUR_AWS_ACCOUNT_ID:layer:ffmpeg:VERSION`
- Tagger mode: `course_model`

### GCP

- Project: `YOUR_GCP_PROJECT_ID`
- Region: `australia-southeast1`
- Cloud Function: `aussie-ecolens-mirror`
- Function URL: `https://YOUR_MIRROR_SERVICE_URL`
- Mirror bucket: `gs://YOUR_MIRROR_BUCKET`
- Cloud Run model service: `aussie-ecolens-model`
- Model service URL: `https://YOUR_MODEL_SERVICE_URL`
- Model bucket: `gs://YOUR_MODEL_BUCKET`
- Demo stability setting: Cloud Run model service `min-instances=1`

## Local UI

Start the UI:

```bash
cd AussieEcoLens
python3 -m src.aussie_ecolens.server
```

Open:

```text
http://127.0.0.1:8080
```

The UI is configured in cloud mode through `web/config.js`, so sign-up and sign-in use AWS Cognito Hosted UI and protected API calls go to API Gateway.

## Local Course ML Model Demo

The supplied course model is installed locally in:

```text
AussieEcoLens/.venv312
```

Run the standalone model test:

```bash
.venv312/bin/python scripts/course_model_predict.py \
  test_images/Casuarius_casuarius_2.JPG \
  --model course_models/model.pt \
  --detector course_models/mdv5a.pt
```

Verified output:

```json
{
  "species": "Casuarius_casuarius",
  "confidence": 1.0
}
```

Run the local app with the supplied course model:

```bash
LOCAL_TAGGER_MODE=course python3 -m src.aussie_ecolens.server
```

Verified local app result:

```text
filename: Casuarius_casuarius_2.JPG
media_type: image
tags: {'casuarius_casuarius': 1}
thumbnail_url: /var/storage/thumbnails/...
```

## Demonstration Flow

1. Open `http://127.0.0.1:8080`.
2. Sign up through Cognito Hosted UI.
3. Sign in through Cognito.
4. Upload a test image, for example `Alectura_lathami_1.JPG`.
5. Show upload result with:
   - `media_type: image`
   - detected tags
   - original file URL
   - thumbnail URL
6. Upload the same image again and show `duplicate: true`.
7. Query by tag JSON, for example:

```json
{"alectura_lathami": 1}
```

8. Query by species, for example:

```text
alectura_lathami
```

9. Click/open the thumbnail URL and show the full image URL can be retrieved.
10. Upload a query-only file and show matching URLs are returned without storing the query file.
11. Add a manual tag to a media URL.
12. Query the new manual tag.
13. Delete a media URL and show it no longer appears in query results.
14. Upload a short video and show `frame_urls` are returned.
15. Show GCP mirror metadata in `gs://YOUR_MIRROR_BUCKET/media-metadata/`.

## Verified Cloud Results

### Unauthenticated Access Control

Unauthenticated API query returned:

```text
401 Unauthorized
```

### Authenticated Image Upload

Verified AWS upload:

```json
{
  "duplicate": false,
  "filename": "Alectura_lathami_1.JPG",
  "media_type": "image",
  "tags": {
    "alectura_lathami": 1
  },
  "has_thumbnail_url": true
}
```

### Tag Query

Verified query:

```json
{
  "result_count": 1,
  "first_filename": "Alectura_lathami_1.JPG",
  "first_tags": {
    "alectura_lathami": 1
  }
}
```

### Video 1 FPS Extraction

Verified AWS video upload:

```json
{
  "media_type": "video",
  "tags": {
    "casuarius_casuarius": 3
  },
  "frame_url_count": 3
}
```

The video filename used for verification did not contain the species name. AWS extracted frames with ffmpeg, sent the frames to the GCP course model service, and stored the model-derived tag count in DynamoDB.

Frame objects were stored under:

```text
s3://YOUR_THUMBNAIL_BUCKET/video-frames/{checksum}/frame-0001.jpg
s3://YOUR_THUMBNAIL_BUCKET/video-frames/{checksum}/frame-0002.jpg
s3://YOUR_THUMBNAIL_BUCKET/video-frames/{checksum}/frame-0003.jpg
```

### Multi-Cloud GCP Mirror

Verified AWS upload mirrored into GCP:

```json
{
  "checksum": "7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b",
  "filename": "Felis_catus_2.JPG",
  "media_type": "image",
  "tags": {
    "felis_catus": 1
  },
  "storage_url": "s3://YOUR_MEDIA_BUCKET/originals/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b_Felis_catus_2.JPG",
  "thumbnail_storage_url": "s3://YOUR_THUMBNAIL_BUCKET/thumbnails/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b.jpg"
}
```

GCP object:

```text
gs://YOUR_MIRROR_BUCKET/media-metadata/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b.json
```

### Notification Verification

Watched-tag records and in-app notification records were verified in DynamoDB and through `/api/notifications`:

```json
{
  "status": 200,
  "notification_count": 1,
  "latest": {
    "channels": ["in_app", "sns", "smtp"],
    "tag": "casuarius_casuarius"
  }
}
```

The final deployment uses `EMAIL_NOTIFICATION_MODE=both`, so the same watched-tag event creates an in-app record, publishes to SNS, and sends SMTP email through a Gmail App Password. The recipient confirmed the SMTP email was received.
