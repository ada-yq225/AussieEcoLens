# Aussie EcoLens

A local-first implementation of the FIT5225 2026 S1 Assignment 2 wildlife media platform.

The project is built in stages:

1. Local demo with the same API shape as the cloud system.
2. Automated workflow tests for upload, deduplication, tagging, querying, editing, deletion, and notifications.
3. Cloud deployment on AWS plus GCP.

## Local Demo

The local demo uses:

- Python standard library HTTP server
- SQLite database
- Local filesystem storage
- Pillow for image thumbnails
- A deterministic demo tagger that recognises species from filenames such as `koala2_wombat1.jpg`

Run it:

```bash
python3 -m src.aussie_ecolens.server
```

Run it with the supplied course ML model:

```bash
LOCAL_TAGGER_MODE=course python3 -m src.aussie_ecolens.server
```

The course model mode expects `.venv312` to exist and the supplied files to be available at:

- `/Users/yq225/Downloads/作业资料/AussieEcoLense/model.pt`
- `/Users/yq225/Downloads/作业资料/AussieEcoLense/mdv5a.pt`

The Python 3.12 ML environment is local-only and ignored by git:

```text
/Users/yq225/AussieEcoLens/.venv312
```

Then open:

```text
http://127.0.0.1:8080
```

Run the workflow tests:

```bash
python3 -m unittest discover -s tests
```

Final manual testing instructions are in:

```text
README_TESTING.md
```

## Demo Credentials

The local demo has mock authentication so the complete workflow can be tested before touching cloud services.

Create a user through the UI, or call:

```bash
POST /api/auth/signup
```

## Cloud Deployment

The final cloud version uses:

- AWS Cognito, API Gateway, Lambda, S3, DynamoDB, SNS, and an ffmpeg Lambda layer.
- GCP Cloud Run for the supplied course ML model (`model.pt` + `mdv5a.pt`).
- GCP Cloud Storage for mirrored AWS upload metadata.

In cloud mode, image uploads and video frames are tagged by the deployed course ML model. Video uploads are sampled at roughly one frame per second before model inference.

Step-by-step final testing instructions are in:

```text
README_TESTING.md
```
