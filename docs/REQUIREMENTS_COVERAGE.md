# FIT5225 A2 Requirements Coverage

This document maps the assignment requirements to the implemented Aussie EcoLens system and gives concrete demo evidence for each item.

## Authentication and Authorisation, 10%

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Use AWS Cognito for authentication and authorisation | Cognito User Pool, Hosted UI, JWT authoriser on API Gateway | `infra/aws/template.yaml`, `web/config.js` |
| Record email, first name, last name, and password for new accounts | Cognito user attributes and Hosted UI sign-up | Sign-up page collects required fields |
| Block pages and endpoints for unauthenticated users | UI hides app workflows until sign-in; API Gateway authoriser rejects unauthenticated `/api/*` calls | Latest smoke test returned `401` for unauthenticated API access |
| Allow sign-in, upload, query, results, and sign-out after authentication | Cloud UI uses Cognito redirect flow and sends JWT bearer tokens to API Gateway | `web/app.js` |
| Fine-grained permissions | Lambda execution role grants scoped S3, DynamoDB, SNS, and GCP-calling permissions | `infra/aws/template.yaml` |

## Core Functionalities, 50%

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Flexible model handling | GCP Cloud Run model service loads classifier and detector from configurable Cloud Storage blob paths | `src/cloud/model_service/app.py`, `scripts/deploy_model_service.sh` |
| Upload file to cloud storage | Authenticated `/api/upload` stores originals in S3 | `src/cloud/aws/handlers.py` |
| Trigger serverless processing on upload | Lambda API path processes direct uploads; S3 EventBridge upload trigger is also configured | `infra/aws/template.yaml` |
| Deduplication by checksum | SHA-256 checksum becomes the media primary key and duplicate uploads return existing metadata | `put_media` in `src/cloud/aws/handlers.py` |
| Image thumbnails | Lambda creates compressed thumbnails with preserved aspect ratio and stores them in a thumbnail S3 bucket | `create_thumbnail` in `src/cloud/aws/handlers.py` |
| Species tagging using supplied ML model | AWS Lambda calls GCP Cloud Run; Cloud Run runs MegaDetector plus the supplied classifier | `detect_with_course_model`, `src/cloud/model_service/app.py` |
| Store file type, tags, storage URL, thumbnail URL | DynamoDB stores metadata; API responses include signed URLs and canonical storage URLs | `media_payload` in `src/cloud/aws/handlers.py` |
| Video processing at 1 frame/second | Lambda uses ffmpeg `fps=1`, stores extracted frames, and sends each frame to the same model | `extract_video_frames` in `src/cloud/aws/handlers.py` |
| Query by tag counts with AND logic | `/api/query/tags` requires all requested tags to meet minimum counts | `search_by_tags` in `src/cloud/aws/handlers.py` |
| Query by species | `/api/query/species` returns media containing at least one requested species | `src/cloud/aws/handlers.py` |
| Query full image URL from thumbnail URL | `/api/query/thumbnail` maps a thumbnail S3 URL back to the original media URL | `media_from_url` in `src/cloud/aws/handlers.py` |
| Query by tags of an uploaded file without storing it | `/api/query/file` detects tags from the submitted file and searches existing records only | `src/cloud/aws/handlers.py` |
| Manual bulk tag add/remove | `/api/tags/edit` accepts URLs, tags, and operation `1` or `0` | `src/cloud/aws/handlers.py` |
| Delete files and metadata | `/api/delete` removes originals, thumbnails, video frames, and DynamoDB metadata | `src/cloud/aws/handlers.py` |
| Tag-based notifications | Watch records create in-app notification records and publish through SNS plus SMTP email | Latest smoke test returned channels `["in_app", "sns", "smtp"]` |

## User Interface, 20%

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Web UI supports all core functionality | Single-page UI covers sign-in, image/video upload, queries, thumbnail lookup, query-by-file, tag edit, delete, and notifications | `web/index.html`, `web/app.js`, `web/styles.css` |
| View query results | Result cards display thumbnails, tag chips, media type, frame previews, and copyable URLs | `renderResults` in `web/app.js` |
| Notification interaction | Users can watch tags and refresh in-app notifications from the UI | Notifications panel in `web/index.html` |

## Demo and Reports, 20%

| Requirement | Prepared asset | Status |
| --- | --- | --- |
| Multi-cloud architecture diagram | `docs/ARCHITECTURE.md` gives the exact architecture and a Mermaid diagram source | Ready for report conversion with official AWS/GCP icons |
| Team contribution table | `docs/TEAM_REPORT_OUTLINE.md` includes the required three-column table | Requires real team names, student IDs, and percentages |
| User guide | `README.md` and `README_TESTING.md` | Ready |
| Source code repository link | GitHub repository `ada-yq225/AussieEcoLens` | Ready; keep private and share with teaching team |
| Individual report | `docs/INDIVIDUAL_REPORT_TEMPLATE.md` | Requires each student's own reflection |

## Verified Final Smoke Test

The latest cloud test verified:

```json
{
  "image_upload": {
    "duplicate": false,
    "media_type": "image",
    "tags": {
      "casuarius_casuarius": 1
    },
    "thumbnail_url_present": true,
    "full_url_present": true
  },
  "notifications": {
    "latest_tag": "casuarius_casuarius",
    "latest_channels": ["in_app", "sns", "smtp"]
  }
}
```

