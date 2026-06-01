# Aussie EcoLens

A local-first implementation of the FIT5225 2026 S1 Assignment 2 wildlife media platform.

The project is built in stages:

1. Local demo with the same API shape as the cloud system.
2. Automated workflow tests for upload, deduplication, tagging, querying, editing, deletion, and notifications.
3. Cloud deployment plan for AWS plus a second cloud provider.

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

Then open:

```text
http://127.0.0.1:8080
```

Run the workflow tests:

```bash
python3 -m unittest discover -s tests
```

## Demo Credentials

The local demo has mock authentication so the complete workflow can be tested before touching cloud services.

Create a user through the UI, or call:

```bash
POST /api/auth/signup
```

## Cloud Accounts Needed Later

The real cloud phase will require manual login or credentials for:

- AWS Academy or AWS account with access to Cognito, IAM, S3, Lambda, API Gateway, DynamoDB, and SNS.
- A second cloud provider account, recommended GCP, with access to Cloud Storage and Cloud Functions or Cloud Run.
- Email confirmation access for Cognito and SNS notification testing.

No real cloud resources are created by the local demo.
