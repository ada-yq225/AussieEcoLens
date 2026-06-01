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
- Optional Rekognition

Install/login requirements:

```bash
aws configure sso
aws sts get-caller-identity
sam --version
```

If the AWS Academy environment does not support SSO, use the credentials flow provided by the Academy console.

### GCP

Required services:

- Cloud Storage
- Cloud Functions gen2 or Cloud Run functions

Install/login requirements:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Deployment Order

Deploy GCP first so AWS can call the GCP mirror endpoint.

```bash
export GCP_PROJECT_ID=YOUR_PROJECT_ID
export GCP_REGION=australia-southeast1
export GCP_BUCKET=YOUR_UNIQUE_BUCKET_NAME
export GCP_SHARED_SECRET=choose-a-long-random-secret
scripts/deploy_gcp.sh
```

The script prints the GCP function URL. Use that as `GCP_MIRROR_ENDPOINT` for AWS.

```bash
export STACK_NAME=aussie-ecolens
export AWS_REGION=ap-southeast-2
export APP_URL=http://127.0.0.1:8080/
export NOTIFICATION_EMAIL=YOUR_EMAIL
export TAGGER_MODE=filename
export GCP_MIRROR_ENDPOINT=THE_GCP_FUNCTION_URL
export GCP_SHARED_SECRET=the-same-secret
export FFMPEG_LAYER_ARN=
scripts/deploy_aws.sh
```

Use `TAGGER_MODE=rekognition` only after you confirm that your AWS account has Rekognition access and you accept possible service cost.

Set `FFMPEG_LAYER_ARN` to a Lambda layer that contains `/opt/bin/ffmpeg` for final video compliance.

## After AWS Deploy

1. Confirm the SNS subscription email.
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

The teaching material in `/Users/yq225/Downloads/作业资料/AussieEcoLense.zip` supplies:

- `mdv5a.pt`: MegaDetector.
- `model.pt`: fine-tuned SpeciesNet classifier.
- `labels.txt`: supported species labels.
- `batch.py`: reference batch pipeline.

Local model verification script:

```bash
python3.12 -m pip install megadetector tqdm onnx2torch
python3.12 scripts/course_model_predict.py /Users/yq225/Downloads/作业资料/test_images/Casuarius_casuarius_1.JPG \
  --model /Users/yq225/Downloads/作业资料/AussieEcoLense/model.pt \
  --detector /Users/yq225/Downloads/作业资料/AussieEcoLense/mdv5a.pt
```

For AWS Lambda, the supplied model package is too large for the simple zip-based Lambda path. Use one of these final-deployment options:

- Lambda container image with torch, megadetector, `mdv5a.pt`, and `model.pt`.
- EFS-mounted model files with a Lambda function configured for EFS.
- A secondary serverless container endpoint such as Cloud Run for model inference.

The current SAM template remains deployable with `TAGGER_MODE=filename` or `TAGGER_MODE=rekognition`.

## Security Controls

- API Gateway is configured with a Cognito JWT authorizer as the default authorizer.
- The local demo blocks protected APIs unless a bearer token from local sign-in is provided.
- The cloud UI redirects users through Cognito Hosted UI and stores Cognito tokens locally for authenticated API calls.
- S3, DynamoDB, SNS, and Rekognition access are granted to Lambda through scoped SAM policies, not broad user credentials.

## Video Processing

For final video compliance, set `FFMPEG_LAYER_ARN` to a Lambda layer that contains `/opt/bin/ffmpeg`.

When configured, video uploads are processed as follows:

1. Lambda writes the uploaded video to `/tmp`.
2. `ffmpeg -vf fps=1` extracts one JPEG frame per second.
3. Frames are uploaded to the thumbnail bucket under `video-frames/{checksum}/`.
4. API responses include `frame_urls` and `frame_storage_urls`.
5. Deleting the video also deletes extracted frames.

## Important Limitations To Resolve Before Submission

- Cloud deployment still requires AWS/GCP login and CLI tools on the machine.
- Set `FFMPEG_LAYER_ARN` to an ffmpeg Lambda layer ARN before the final cloud demo.
- Replace `APP_URL=http://127.0.0.1:8080/` with the final hosted UI URL if you deploy the frontend publicly.
