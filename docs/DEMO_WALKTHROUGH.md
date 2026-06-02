# Aussie EcoLens Demo Walkthrough

This document is the working demo guide for the final assignment demonstration.

## Deployed Cloud Resources

### AWS

- Region: `ap-southeast-2`
- CloudFormation stack: `aussie-ecolens`
- API Gateway URL: `https://e4a7ina4v9.execute-api.ap-southeast-2.amazonaws.com`
- Cognito User Pool: `ap-southeast-2_WRgsNIPqw`
- Cognito Client ID: `3mqkk0qovhrtse73noholbdbnr`
- Cognito Domain: `https://aussie-ecolens-828876761072-ap-southeast-2.auth.ap-southeast-2.amazoncognito.com`
- Media S3 bucket: `aussie-ecolens-mediabucket-1e7c2q6ajljd`
- Thumbnail/frame S3 bucket: `aussie-ecolens-thumbnailbucket-uqarv73svbxs`
- DynamoDB table: `aussie-ecolens-metadata`
- SNS topic: `arn:aws:sns:ap-southeast-2:828876761072:aussie-ecolens-tag-notifications`
- ffmpeg Lambda layer: `arn:aws:lambda:ap-southeast-2:175033217214:layer:ffmpeg:1`
- Tagger mode: `course_model`

### GCP

- Project: `aussie-ecolens-raywu361`
- Region: `australia-southeast1`
- Cloud Function: `aussie-ecolens-mirror`
- Function URL: `https://aussie-ecolens-mirror-hzmou43rsa-ts.a.run.app`
- Mirror bucket: `gs://aussie-ecolens-raywu361-mirror`
- Cloud Run model service: `aussie-ecolens-model`
- Model service URL: `https://aussie-ecolens-model-hzmou43rsa-ts.a.run.app`
- Model bucket: `gs://aussie-ecolens-raywu361-models`
- Demo stability setting: Cloud Run model service `min-instances=1`

## Local UI

Start the UI:

```bash
cd /Users/yq225/AussieEcoLens
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
/Users/yq225/AussieEcoLens/.venv312
```

Run the standalone model test:

```bash
.venv312/bin/python scripts/course_model_predict.py \
  /Users/yq225/Downloads/作业资料/test_images/Casuarius_casuarius_2.JPG \
  --model /Users/yq225/Downloads/作业资料/AussieEcoLense/model.pt \
  --detector /Users/yq225/Downloads/作业资料/AussieEcoLense/mdv5a.pt
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
15. Show GCP mirror metadata in `gs://aussie-ecolens-raywu361-mirror/media-metadata/`.

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
s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/{checksum}/frame-0001.jpg
s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/{checksum}/frame-0002.jpg
s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/{checksum}/frame-0003.jpg
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
  "storage_url": "s3://aussie-ecolens-mediabucket-1e7c2q6ajljd/originals/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b_Felis_catus_2.JPG",
  "thumbnail_storage_url": "s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/thumbnails/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b.jpg"
}
```

GCP object:

```text
gs://aussie-ecolens-raywu361-mirror/media-metadata/7a97e0bb6c81620aa84244d4b543c815ab7930e00220ad28129a20b778f9e70b.json
```

### Notification Verification

Watched-tag records and in-app notification records were verified in DynamoDB and through `/api/notifications`:

```json
{
  "status": 200,
  "notification_count": 2,
  "latest": {
    "channels": ["in_app", "sns"],
    "tag": "casuarius_casuarius"
  }
}
```

SNS email delivery still requires the recipient to confirm the AWS SNS subscription email. As a deployable alternative, the Lambda notification path now supports SMTP with `EMAIL_NOTIFICATION_MODE=smtp` or `both` plus `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM`.
