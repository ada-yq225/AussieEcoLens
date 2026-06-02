# Aussie EcoLens Product Manual

Aussie EcoLens is a multi-cloud wildlife media management system built for the FIT5225 2026 S1 Assignment 2 requirements. It lets authenticated users upload wildlife images and videos, automatically tag animals with the supplied course ML model, query media by tags or species, retrieve full images from thumbnail URLs, edit tags, delete media, and receive watched-tag notifications.

The final deployment uses AWS for the application backend and GCP for the course ML inference service and cross-cloud metadata mirroring.

## Executive Summary

The system supports the complete coursework workflow:

- User registration and sign-in with AWS Cognito.
- Protected API access through API Gateway JWT authorisation.
- Image upload, thumbnail generation, duplicate detection, and tag storage.
- Video upload with ffmpeg frame extraction at approximately one frame per second.
- Real animal recognition with the supplied course model, not filename guessing.
- Tag-count queries such as `{"casuarius_casuarius": 3}`.
- Species queries such as `casuarius_casuarius`.
- Thumbnail URL to full image URL lookup.
- Query-by-file without permanently storing the query file.
- Manual tag add/remove.
- Media deletion from S3, DynamoDB, and extracted-frame storage.
- Watched-tag notifications through in-app records, SNS, and optional SMTP email.
- Metadata mirroring from AWS to GCP Cloud Storage.

## Deployed Cloud Architecture

### AWS Application Layer

- AWS Cognito User Pool handles user registration, email attributes, sign-in, and JWTs.
- Amazon API Gateway exposes protected REST-style endpoints under `/api/*`.
- AWS Lambda implements upload, query, tag editing, deletion, notifications, and cloud mirroring.
- Amazon S3 stores original media files.
- A second S3 bucket stores image thumbnails and extracted video frames.
- Amazon DynamoDB stores media metadata, tags, watch records, and notification records.
- Amazon SNS is configured for email-topic notification delivery.
- An ffmpeg Lambda layer extracts video frames.

### GCP Model and Mirror Layer

- GCP Cloud Run hosts the course ML inference service.
- GCP Cloud Storage stores `model.pt` and `mdv5a.pt`.
- GCP Cloud Storage also stores mirrored metadata JSON from AWS uploads.
- The model service is protected by a shared secret header and is called only by AWS Lambda.

### Current Production Endpoints

```text
Web UI:              http://127.0.0.1:8080/
AWS API Gateway:     https://e4a7ina4v9.execute-api.ap-southeast-2.amazonaws.com
Cognito Domain:      https://aussie-ecolens-828876761072-ap-southeast-2.auth.ap-southeast-2.amazoncognito.com
GCP Model Service:   https://aussie-ecolens-model-hzmou43rsa-ts.a.run.app
GCP Mirror Function: https://aussie-ecolens-mirror-hzmou43rsa-ts.a.run.app
```

## How The ML Tagging Works

### Image Workflow

1. The user uploads an image through the web UI.
2. The browser compresses large images before cloud upload when needed.
3. API Gateway passes the authenticated request to Lambda.
4. Lambda stores the original image in S3.
5. Lambda creates a thumbnail and stores it in the thumbnail S3 bucket.
6. Lambda sends the image bytes to the GCP Cloud Run model service.
7. The model service runs MegaDetector (`mdv5a.pt`) to find animal bounding boxes.
8. It crops detected animals and classifies them with the supplied course classifier (`model.pt`).
9. Lambda writes the returned tag counts to DynamoDB.
10. AWS mirrors the metadata JSON to GCP Cloud Storage.

### Video Workflow

1. The user switches to Video mode and uploads a video.
2. Lambda stores the original video in S3.
3. Lambda runs ffmpeg with `fps=1`.
4. Extracted frames are stored in the thumbnail/frame bucket.
5. Each extracted frame is sent to the same GCP course model service.
6. The model service classifies each frame.
7. Lambda aggregates frame predictions into tag counts.

For example, a 3-second video containing the same animal in each sampled frame can return:

```json
{
  "casuarius_casuarius": 3
}
```

This means the video has three sampled frames classified as `casuarius_casuarius`.

## Supported Media

### Images

Supported image extensions:

```text
.jpg, .jpeg, .png, .gif, .webp
```

The course model is most reliable on the provided wildlife camera-trap images. The UI still accepts other supported image formats, but model accuracy depends on whether the detector can find an animal.

### Videos

Supported video extensions:

```text
.mp4, .mov, .avi, .mkv, .webm, .m4v, .mpg, .mpeg, .3gp, .3g2, .wmv, .flv, .ts, .m2ts, .ogv
```

Actual decoding depends on ffmpeg codec support in the Lambda layer. There is no hard 3-second assignment limit. The demo uses short videos because direct API Gateway uploads are designed for small coursework files; very large videos can exceed request-size or execution-time limits.

## User Guide

### 1. Start The Web UI

From the project root:

```bash
cd /Users/yq225/AussieEcoLens
python3 -m src.aussie_ecolens.server
```

Open:

```text
http://127.0.0.1:8080/
```

The current `web/config.js` is in cloud mode. Sign-in and sign-up redirect to AWS Cognito, and API requests go to API Gateway.

### 2. Sign In

Use the Cognito Hosted UI:

1. Click sign in or sign up.
2. Enter email, password, first name, and last name when registering.
3. Return to the app after Cognito redirects back.
4. Confirm the page shows your name and a `Sign out` button.

Protected pages and APIs reject unauthenticated requests. The latest cloud smoke test confirmed unauthenticated API access returns `401`.

### 3. Upload Images

1. Select Image mode.
2. Click `Choose images`.
3. Select one or more images.
4. Click `Upload images`.

Expected output:

- One result card per file.
- A thumbnail preview.
- Model-derived tag chips.
- A hidden `Thumbnail URL` with Show/Hide and Copy controls.
- `Uploaded N files` status.

Example tag output:

```json
{
  "casuarius_casuarius": 1
}
```

### 4. Upload Videos

1. Select Video mode.
2. Click `Choose videos`.
3. Select a short demo video.
4. Click `Upload videos`.

Expected output:

- `media_type` is `video`.
- `Open original video` appears.
- Extracted frame previews appear.
- Frame URL copy buttons appear.
- The tags reflect model predictions from extracted frames.

Example verified output:

```json
{
  "media_type": "video",
  "tags": {
    "casuarius_casuarius": 3
  },
  "frame_url_count": 3
}
```

### 5. Query By Tag Counts

Use `Tag count JSON` for exact count requirements:

```json
{"casuarius_casuarius": 3}
```

This returns media whose stored tag count is at least the requested value. This is useful for video results where repeated frame detections produce counts above 1.

### 6. Query By Species

Use the Species input:

```text
casuarius_casuarius
```

This returns all media with at least one matching tag.

### 7. Thumbnail URL To Full Image URL

1. Copy a result card's `Thumbnail URL`.
2. Paste it into the Thumbnail URL query box.
3. Click `Get full image`.

Expected output:

- An `Open original image` button.
- A hidden/copyable full image URL.

This matches the assignment requirement that a thumbnail URL can be used to retrieve the full original image URL.

### 8. Query By File Without Storing

Use the `Query by file` area:

1. Select an image.
2. Click `Find matching media`.

Expected output:

- The file is tagged by the model.
- Existing matching media is returned.
- The query-only file is not stored as a new media item.

### 9. Manage Tags

Use `Manage Tags and Files`:

- Add tags to one or more media URLs.
- Remove tags.
- Query the manually added tag afterward to confirm the change.

Manual tags are stored in DynamoDB and participate in the same query system as model-generated tags.

### 10. Delete Media

Paste a full media URL into the delete area and submit.

Expected behavior:

- Original media object is deleted from S3.
- Image thumbnail is deleted.
- Video extracted frames are deleted.
- DynamoDB metadata is deleted.
- The deleted item no longer appears in query results.

## Notifications

The system supports three notification channels.

### In-App Notifications

This is the most reliable channel for assessment because it does not require external email confirmation.

1. Enter watched tags, for example:

```text
casuarius_casuarius
```

2. Enter an email address.
3. Click `Watch`.
4. Upload media that matches the watched tag.
5. The backend creates a notification record in DynamoDB.
6. Click `Refresh notifications` in the UI to display the in-app notification.

The latest smoke test verified that notification records are returned from `/api/notifications` with:

```json
{
  "channels": ["in_app", "sns", "smtp"],
  "tag": "casuarius_casuarius"
}
```

### SNS Email Notifications

AWS SNS is configured and Lambda publishes watched-tag matches to the SNS topic. SNS email delivery requires the recipient to confirm the subscription email. If the recipient does not click the confirmation link, SNS accepts publishes but does not deliver email.

This is why SNS email may be unavailable during the demo even though the backend publish path works.

### SMTP Email Alternative

To avoid SNS subscription confirmation, the project now includes an optional SMTP email channel. It can use Gmail App Password, school SMTP, SendGrid, Mailgun, or any SMTP-compatible provider.

Deploy with SMTP:

```bash
AWS_PROFILE=aussie-ecolens-admin \
AWS_REGION=ap-southeast-2 \
TAGGER_MODE=course_model \
EMAIL_NOTIFICATION_MODE=smtp \
SMTP_HOST=smtp.gmail.com \
SMTP_PORT=587 \
SMTP_USERNAME=your_sender@gmail.com \
SMTP_PASSWORD='your_gmail_app_password' \
SMTP_FROM=your_sender@gmail.com \
SMTP_STARTTLS=true \
FFMPEG_LAYER_ARN='arn:aws:lambda:ap-southeast-2:175033217214:layer:ffmpeg:1' \
GCP_MIRROR_ENDPOINT='https://aussie-ecolens-mirror-hzmou43rsa-ts.a.run.app' \
GCP_SHARED_SECRET='...' \
MODEL_INFERENCE_ENDPOINT='https://aussie-ecolens-model-hzmou43rsa-ts.a.run.app' \
MODEL_SHARED_SECRET='...' \
scripts/deploy_aws.sh
```

Use `EMAIL_NOTIFICATION_MODE=both` to keep SNS and SMTP enabled together. Do not use a normal Gmail password; Gmail requires an App Password for SMTP. The deployment script strips spaces from grouped Gmail App Passwords automatically.

## Cloud Run Cold Start And Demo Stability

The GCP model container is large because it includes PyTorch, MegaDetector, and the course classifier. A cold start can exceed API Gateway's synchronous request window. For a stable live demo, the deployed Cloud Run model service has been set to:

```text
min-instances = 1
```

This keeps one model service instance warm so uploads do not fail on first use. To save cost after assessment, set it back to zero:

```bash
tools/google-cloud-sdk/bin/gcloud run services update aussie-ecolens-model \
  --project=aussie-ecolens-raywu361 \
  --region=australia-southeast1 \
  --min-instances=0
```

To deploy the model service with a chosen value:

```bash
GCP_PROJECT_ID=aussie-ecolens-raywu361 \
GCP_REGION=australia-southeast1 \
MODEL_BUCKET=aussie-ecolens-raywu361-models \
MODEL_SHARED_SECRET='...' \
MODEL_MIN_INSTANCES=1 \
CLASSIFIER_BLOB=course-model/model.pt \
DETECTOR_BLOB=course-model/mdv5a.pt \
DETECTION_THRESHOLD=0.05 \
PREDICTION_THRESHOLD=0.0 \
scripts/deploy_model_service.sh
```

Changing `CLASSIFIER_BLOB` or `DETECTOR_BLOB` points the model service to a different model object in GCP Cloud Storage without changing application source code.

## Verified End-To-End Results

The latest full cloud smoke test verified:

```json
{
  "unauthenticated_api_status": 401,
  "image_upload": {
    "duplicate": false,
    "media_type": "image",
    "tags": {
      "casuarius_casuarius": 1
    },
    "has_thumbnail_url": true
  },
  "duplicate_detected": true,
  "thumbnail_lookup_has_full_url": true,
  "query_by_file_detected_tags": {
    "casuarius_casuarius": 1
  },
  "manual_tag_query_count": 1,
  "delete_status": 200,
  "post_delete_manual_tag_count": 0,
  "video_upload": {
    "duplicate": false,
    "media_type": "video",
    "tags": {
      "casuarius_casuarius": 3
    },
    "frame_url_count": 3
  },
  "tag_count_query_contains_video": true,
  "gcp_mirror_video_tags": {
    "casuarius_casuarius": 3
  },
  "gcp_mirror_video_media_type": "video"
}
```

Notification retrieval was also verified after fixing DynamoDB Decimal JSON serialisation:

```json
{
  "status": 200,
  "notification_count": 2,
  "latest": {
    "channels": ["in_app", "sns", "smtp"],
    "tag": "casuarius_casuarius"
  }
}
```

## Local Development

The local demo uses:

- Python standard library HTTP server.
- SQLite database.
- Local filesystem storage.
- Pillow for image thumbnails.
- Optional course-model tagging using the local Python 3.12 environment.

Run local mode:

```bash
python3 -m src.aussie_ecolens.server
```

Run local mode with the supplied course model:

```bash
LOCAL_TAGGER_MODE=course python3 -m src.aussie_ecolens.server
```

The local ML environment is:

```text
/Users/yq225/AussieEcoLens/.venv312
```

The supplied model files are expected at:

```text
/Users/yq225/Downloads/作业资料/AussieEcoLense/model.pt
/Users/yq225/Downloads/作业资料/AussieEcoLense/mdv5a.pt
```

Run local tests:

```bash
python3 -m unittest discover -s tests
```

## Additional Documentation

- `README_TESTING.md`: step-by-step assessment test checklist.
- `docs/REQUIREMENTS_COVERAGE.md`: assignment requirement-to-implementation mapping.
- `docs/ARCHITECTURE.md`: architecture diagram source and official-icon checklist for the team report.
- `docs/DEMO_WALKTHROUGH.md`: concise demo script and deployed resource list.
- `docs/DEPLOYMENT.md`: deployment notes.
- `docs/ACCEPTANCE_CHECKLIST.md`: requirement coverage checklist.
