# Acceptance Checklist

## Authentication and Authorisation

- [x] AWS Cognito sign-up with email, first name, last name, and password configured in SAM template.
- [x] Email verification flow configured through Cognito.
- [x] Sign-in and sign-out implemented through Cognito Hosted UI in cloud mode.
- [ ] Unauthenticated users blocked from protected pages and APIs.
- [x] Fine-grained SAM IAM policies for S3, DynamoDB, Lambda, SNS, and optional Rekognition.

## File Handling

- [x] Local upload API.
- [x] SHA-256 checksum deduplication.
- [x] Image thumbnail generation with preserved aspect ratio.
- [x] Cloud event trigger on upload configured for S3 object-created events.
- [ ] Video 1 frame/second extraction in cloud or ffmpeg-enabled environment.
- [x] Demo tagging and database insertion.
- [ ] Production teaching-provided ML model integration.

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

## UI

- [x] Local sign-up, sign-in, sign-out UI.
- [x] Upload UI with deduplication feedback.
- [x] Query UI with thumbnail previews and full image links.
- [x] Bulk tag edit and delete UI.
- [x] Notification watch UI.

## Reports and Demo

- [ ] Official multi-cloud architecture diagram.
- [ ] Team contribution table.
- [ ] User guide.
- [ ] Private Git repository link with commits from all members.
- [ ] Individual report.
- [ ] Demo script and Q&A notes.
