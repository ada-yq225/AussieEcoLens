# Acceptance Checklist

## Authentication and Authorisation

- [x] AWS Cognito sign-up with email, first name, last name, and password configured in SAM template.
- [x] Email verification flow configured through Cognito.
- [x] Sign-in and sign-out implemented through Cognito Hosted UI in cloud mode.
- [x] Unauthenticated API access blocked by local bearer-token middleware and AWS API Gateway Cognito authorizer.
- [x] Cloud UI uses Cognito Hosted UI before showing protected workflows.
- [x] Fine-grained SAM IAM policies for S3, DynamoDB, Lambda, SNS, and optional Rekognition.

## File Handling

- [x] Local upload API.
- [x] SHA-256 checksum deduplication.
- [x] Image thumbnail generation with preserved aspect ratio.
- [x] Cloud event trigger on upload configured for S3 object-created events.
- [x] Video 1 frame/second extraction implemented and verified in AWS Lambda with `FFMPEG_LAYER_ARN`; extracted frame URLs are stored and returned.
- [x] Demo tagging and database insertion.
- [x] Production teaching-provided ML model integrated for local final demo via `LOCAL_TAGGER_MODE=course`.

## Queries

- [x] Query by tags with minimum counts and logical AND.
- [x] Query by species.
- [x] Query full-size image URL from thumbnail URL.
- [x] Query by uploaded file tags without permanent storage.
- [x] Bulk manual tag add/remove.
- [x] Delete files, thumbnails, and database records.

## Notifications

- [x] Local notification log for watched tags.
- [x] AWS SNS email notifications configured.
- [ ] SNS email subscription confirmation pending in recipient inbox.

## Multi-Cloud

- [x] GCP Cloud Function deployed as second-cloud mirror endpoint.
- [x] GCP Cloud Storage mirror bucket created.
- [x] AWS Lambda configured to call GCP function after upload.
- [x] AWS-to-GCP metadata mirror verified with `Felis_catus_2.JPG`.

## UI

- [x] Local sign-up, sign-in, sign-out UI.
- [x] Upload UI with deduplication feedback.
- [x] Query UI with thumbnail previews and full image links.
- [x] Bulk tag edit and delete UI.
- [x] Notification watch UI.

## Reports and Demo

- [ ] Official multi-cloud architecture diagram.
- [ ] Team contribution table.
- [x] User guide and demo walkthrough.
- [x] Private Git repository link available through pushed GitHub repo.
- [ ] Individual report.
- [x] Demo script and Q&A notes.
