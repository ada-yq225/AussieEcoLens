# Demo Script

## Architecture Presentation, 3 minutes

1. User signs up and signs in through AWS Cognito.
2. Authenticated requests go through API Gateway with a Cognito authorizer.
3. Media uploads land in S3.
4. S3 events trigger Lambda.
5. Lambda calculates checksum, prevents duplicate metadata, creates thumbnails, extracts video frames when ffmpeg/model runtime is available, detects tags, and writes metadata to DynamoDB.
6. Query APIs read DynamoDB and return thumbnail URLs for images and full URLs for videos.
7. Tag edits and deletions update both storage and database records.
8. Watched tags publish notifications through SNS.
9. GCP is used as the second cloud for mirrored storage or secondary processing.

## Live Demo Flow

1. Sign up a new user and verify email.
2. Sign in.
3. Upload `koala2_wombat1.jpg`.
4. Upload the same file again and show duplicate detection.
5. Query `{"koala": 2, "wombat": 1}` and show AND result.
6. Click thumbnail to open the full image.
7. Query by species `koala`.
8. Upload a short video after `FFMPEG_LAYER_ARN` is configured and show returned `frame_urls`.
9. Upload a query-only image and show matching database results without permanent storage.
10. Add manual tag `dingo` to the uploaded file.
11. Query `dingo`.
12. Subscribe to `koala` notifications and upload/update matching media.
13. Delete the file and show it disappears from query results.

## Expected Q&A Points

- Checksum uses SHA-256 of file content, not filename.
- Multi-tag queries use logical AND.
- Query-file uploads are not persisted.
- UI is a convenience layer over the REST APIs.
- Cognito is mandatory for auth; IAM policies restrict cloud resources.
- Cost is controlled through serverless services, small demo files, and cleanup.
