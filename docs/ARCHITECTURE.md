# Aussie EcoLens Architecture

Use this page as the architecture section source for the team report. For the final PDF, redraw the same component layout with official AWS and Google Cloud architecture icons, because the assignment explicitly asks for official icons in the report.

## Component Diagram

```mermaid
flowchart LR
    User[Authenticated user<br/>Browser UI]
    Cognito[AWS Cognito<br/>Hosted UI and JWT]
    Api[AWS API Gateway<br/>Protected /api/* endpoints]
    Lambda[AWS Lambda<br/>Upload, query, tag edit,<br/>delete, notifications]
    MediaS3[AWS S3<br/>Original media bucket]
    ThumbS3[AWS S3<br/>Thumbnail and frame bucket]
    DDB[AWS DynamoDB<br/>Media, tags, watchers,<br/>notifications]
    SNS[AWS SNS<br/>Tag notification topic]
    SMTP[SMTP Provider<br/>Gmail App Password]
    ModelRun[GCP Cloud Run<br/>Course model service]
    ModelBucket[GCP Cloud Storage<br/>model.pt and mdv5a.pt]
    MirrorRun[GCP Cloud Run Function<br/>Metadata mirror endpoint]
    MirrorBucket[GCP Cloud Storage<br/>Mirrored metadata JSON]

    User --> Cognito
    Cognito --> User
    User -->|JWT bearer token| Api
    Api --> Lambda
    Lambda --> MediaS3
    Lambda --> ThumbS3
    Lambda --> DDB
    Lambda -->|watched tag match| SNS
    Lambda -->|watched tag match| SMTP
    Lambda -->|image bytes / video frames| ModelRun
    ModelRun --> ModelBucket
    Lambda -->|signed metadata payload| MirrorRun
    MirrorRun --> MirrorBucket
```

## Upload Processing Flow

1. The user signs in with AWS Cognito.
2. The browser sends the JWT to API Gateway.
3. API Gateway authorises the request and invokes Lambda.
4. Lambda calculates a SHA-256 checksum for deduplication.
5. Lambda stores the original media in the media S3 bucket.
6. For images, Lambda creates and stores a thumbnail.
7. For videos, Lambda uses ffmpeg to extract one frame per second and stores frame thumbnails.
8. Lambda sends the image or extracted frames to the GCP Cloud Run model service.
9. The GCP service loads `model.pt` and `mdv5a.pt` from GCP Cloud Storage and returns species tag counts.
10. Lambda writes metadata and tags to DynamoDB.
11. Lambda mirrors metadata to the GCP mirror endpoint.
12. If a watched tag matches, Lambda creates an in-app notification and publishes through SNS and SMTP.

## Official Icon Checklist For Report

Use the official AWS architecture icons for:

- Amazon Cognito
- Amazon API Gateway
- AWS Lambda
- Amazon S3
- Amazon DynamoDB
- Amazon SNS

Use the official Google Cloud architecture icons for:

- Cloud Run
- Cloud Storage

Use a simple external service icon or labelled box for:

- SMTP email provider
- Browser/user

