# Final Deployment Guide

This guide is for the real cloud version.

## What You Need To Log Into

### AWS

Required services:

- Cognito
- IAM
- S3
- Lambda
- API Gateway
- DynamoDB
- SNS
- Optional SMTP provider for email notifications

Install/login requirements:

```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
aws configure sso
aws sts get-caller-identity
sam --version
```

If the AWS Academy environment does not support SSO, use the credentials flow provided by the Academy console.

### GCP

Required services:

- Cloud Storage
- Cloud Run model service
- Cloud Run function for metadata mirroring

Install/login requirements:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Current deployed GCP project:

```text
aussie-ecolens-raywu361
```

## Deployment Order

Deploy GCP first so AWS can call the model service and the mirror endpoint.

### 1. Deploy The GCP Model Service

```bash
export GCP_PROJECT_ID=aussie-ecolens-raywu361
export GCP_REGION=australia-southeast1
export MODEL_BUCKET=aussie-ecolens-raywu361-models
export MODEL_SHARED_SECRET=choose-a-long-random-secret
export MODEL_MIN_INSTANCES=1
export CLASSIFIER_BLOB=course-model/model.pt
export DETECTOR_BLOB=course-model/mdv5a.pt
scripts/deploy_model_service.sh
```

The script uploads the supplied model files to GCP Cloud Storage if they are not already present, then deploys the Cloud Run model service. To switch to a newer model version, upload the new files to GCP Storage and change `CLASSIFIER_BLOB` or `DETECTOR_BLOB`; no source-code change is required.

Current deployed GCP model endpoint:

```text
https://aussie-ecolens-model-hzmou43rsa-ts.a.run.app
```

### 2. Deploy The GCP Mirror Function

```bash
export GCP_PROJECT_ID=YOUR_PROJECT_ID
export GCP_REGION=australia-southeast1
export GCP_BUCKET=aussie-ecolens-raywu361-mirror
export GCP_SHARED_SECRET=choose-a-long-random-secret
scripts/deploy_gcp.sh
```

The script prints the GCP function URL. Use that as `GCP_MIRROR_ENDPOINT` for AWS.

Current deployed GCP endpoint:

```text
https://aussie-ecolens-mirror-hzmou43rsa-ts.a.run.app
```

### 3. Deploy AWS

```bash
export STACK_NAME=aussie-ecolens
export AWS_REGION=ap-southeast-2
export APP_URL=http://127.0.0.1:8080/
export NOTIFICATION_EMAIL=YOUR_EMAIL
export TAGGER_MODE=course_model
export GCP_MIRROR_ENDPOINT=THE_GCP_FUNCTION_URL
export GCP_SHARED_SECRET=the-same-secret
export MODEL_INFERENCE_ENDPOINT=https://aussie-ecolens-model-hzmou43rsa-ts.a.run.app
export MODEL_SHARED_SECRET=the-model-secret
export EMAIL_NOTIFICATION_MODE=both
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=YOUR_SMTP_SENDER
export SMTP_PASSWORD=YOUR_APP_PASSWORD
export SMTP_FROM=YOUR_SMTP_SENDER
export FFMPEG_LAYER_ARN=arn:aws:lambda:ap-southeast-2:175033217214:layer:ffmpeg:1
scripts/deploy_aws.sh
```

`SMTP_PASSWORD` may contain Gmail's visual grouping spaces; `scripts/deploy_aws.sh` removes whitespace before deploying.

## After AWS Deploy

1. Confirm the SNS subscription email if you want SNS email delivery.
2. Start the local UI:

```bash
python3 -m src.aussie_ecolens.server
```

3. Open `http://127.0.0.1:8080`.
4. Sign up/sign in through Cognito.
5. Run the demo workflow.

## Model Choice

The current deployable cloud code supports:

- `filename`: deterministic demo tagger for controlled demo files.
- `rekognition`: AWS Rekognition DetectLabels.
- `course_model`: final mode. AWS Lambda calls the GCP Cloud Run model service using the supplied MegaDetector and classifier.

The teaching material in `course_models.zip` supplies:

- `mdv5a.pt`: MegaDetector.
- `model.pt`: fine-tuned SpeciesNet classifier.
- `labels.txt`: supported species labels.
- `batch.py`: reference batch pipeline.

Local model verification script:

```bash
python3.12 -m pip install megadetector tqdm onnx2torch
python3.12 scripts/course_model_predict.py test_images/Casuarius_casuarius_1.JPG \
  --model course_models/model.pt \
  --detector course_models/mdv5a.pt
```

The final deployment uses the Cloud Run option because the supplied model package is too large for a simple zip-based Lambda function. AWS Lambda stays small and serverless, while the model container runs in GCP with Python 3.12, PyTorch, torchvision, MegaDetector, and onnx2torch installed.

## Security Controls

- API Gateway is configured with a Cognito JWT authorizer as the default authorizer.
- The local demo blocks protected APIs unless a bearer token from local sign-in is provided.
- The cloud UI redirects users through Cognito Hosted UI and stores Cognito tokens locally for authenticated API calls.
- S3, DynamoDB, SNS, and Rekognition access are granted to Lambda through scoped SAM policies, not broad user credentials.

## Video Processing

For final video compliance, `FFMPEG_LAYER_ARN` is set to a Lambda layer that contains `/opt/bin/ffmpeg`.

When configured, video uploads are processed as follows:

1. Lambda writes the uploaded video to `/tmp`.
2. `ffmpeg -vf fps=1` extracts one JPEG frame per second.
3. Frames are uploaded to the thumbnail bucket under `video-frames/{checksum}/`.
4. API responses include `frame_urls` and `frame_storage_urls`.
5. Deleting the video also deletes extracted frames.

Verified cloud result:

```text
media_type: video
frame_url_count: 3
frame_storage_urls:
- s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/.../frame-0001.jpg
- s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/.../frame-0002.jpg
- s3://aussie-ecolens-thumbnailbucket-uqarv73svbxs/video-frames/.../frame-0003.jpg
```

The current AWS deployment uses the public ffmpeg layer:

```text
arn:aws:lambda:ap-southeast-2:175033217214:layer:ffmpeg:1
```

## Final Notes

- Cloud deployment still requires AWS/GCP login and CLI tools on the machine.
- Keep the GCP Cloud Run model service at `min-instances=1` for the live demo to avoid cold-start timeouts.
- Set the model service back to `min-instances=0` after marking to reduce cost.
- Replace `APP_URL=http://127.0.0.1:8080/` with the hosted frontend URL if you deploy the frontend publicly.
