# GCP Secondary Cloud Setup

The assignment requires at least two major cloud providers. This project uses AWS for the main authenticated API and GCP as the secondary cloud.

Recommended GCP role:

- Mirror uploaded original files or processed thumbnails into a GCP Cloud Storage bucket.
- Optionally run a Cloud Function or Cloud Run endpoint that receives a signed request from AWS Lambda and records the mirror result.

Manual steps:

1. Create or select a GCP project.
2. Enable Cloud Storage and Cloud Functions or Cloud Run.
3. Create a bucket in `australia-southeast1`.
4. Create a service account with minimal bucket write/read permissions.
5. Export the service account JSON locally and set `GCP_SERVICE_ACCOUNT_JSON`.
6. Deploy the secondary function from `src/cloud/gcp`.

Do not commit the service account JSON file.

