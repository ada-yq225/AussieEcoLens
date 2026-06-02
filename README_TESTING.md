# Aussie EcoLens Testing README

Use this checklist to verify the final demo from a clean browser session.

## 1. Start the Web App

From the project root:

```bash
cd /Users/yq225/AussieEcoLens
python3 -m src.aussie_ecolens.server
```

Open:

```text
http://127.0.0.1:8080/
```

Expected result:

- The Aussie EcoLens page loads.
- In cloud mode, sign-up/sign-in redirects to AWS Cognito.
- After sign-in, the page shows your first and last name and a `Sign out` button.

## 2. Batch Upload Images

In the `Upload Images` panel:

1. Click `Choose images`.
2. Select multiple files, for example:

```text
Alectura_lathami_1.JPG
Alectura_lathami_2.JPG
Casuarius_casuarius_2.JPG
Felis_catus_2.JPG
```

3. Click `Upload images`.

Expected result:

- The status changes through `Uploading 0/N`, `Uploading 1/N`, and so on.
- When complete, the status shows `Uploaded N files`.
- The `Results` section shows one card per file.
- Large image files are automatically compressed in the browser before cloud upload.
- In the deployed cloud version, tags come from the supplied course ML model running on GCP Cloud Run, not from filenames.
- Each successful card should include:
  - filename
  - detected tags
  - thumbnail image
  - `Thumbnail URL`

Example correct tags:

```json
{"alectura_lathami": 1}
{"casuarius_casuarius": 1}
{"felis_catus": 1}
```

Use the Image/Video mode switch in the upload section. The controls are separated for clarity, but both modes feed the same Results area, query APIs, manual tag editor, delete workflow, and GCP mirror.

## 3. Duplicate Detection

Upload one of the same files again.

Expected result:

- The upload still returns a media card.
- The status may include `duplicate`.
- The record points to the existing media object instead of creating a new duplicate metadata record.

## 4. Query by Tag Counts

In `Tag count JSON`, enter:

```json
{"alectura_lathami": 1}
```

Click `Find by tags`.

Expected result:

- The results include uploaded Alectura images.
- Results include thumbnails and full URLs.

For a multi-tag AND query, enter a JSON object with more than one tag:

```json
{"koala": 2, "wombat": 1}
```

Expected result:

- A media item is returned only if it has all requested tags with at least the requested counts.

## 5. Query by Species

In `Species`, enter:

```text
alectura_lathami
```

Click `Find species`.

Expected result:

- Uploaded media tagged `alectura_lathami` appears.

## 6. Thumbnail to Full Image

Copy `Thumbnail URL` from a result card and paste it into the `Thumbnail URL` query box.

Click `Get full image`.

Expected result:

- The result returns a signed full image URL.
- Opening the URL shows the original uploaded media.
- Upload/query result cards show thumbnail URLs first; the full image URL is displayed after this lookup step.
- The copied input should come from the result card section labelled `Thumbnail URL`, not the `Full image URL` section.

## 7. Query by File Without Storing

In `Query by file`:

1. Select an image file.
2. Click `Find matching media`.

Expected result:

- The app detects tags from the query file.
- Matching existing media appears in results.
- The query-only file is not permanently stored as a new upload.

## 8. Manual Tag Edit

In `Manage Tags and Files`:

1. Paste a full image URL into `URLs, one per line`.
2. Enter:

```text
demo_tag
```

3. Keep operation as `Add`.
4. Click `Apply tag change`.

Expected result:

- The updated media appears in results.
- Querying species `demo_tag` returns that media.

To remove the tag, use the same URL and tag, set operation to `Remove`, then submit.

## 9. Delete Media

In `Delete files`:

1. Paste the full image URL.
2. Click `Delete files`.

Expected result:

- The response includes a deleted checksum/id.
- Querying for that media's tag no longer returns the deleted record.
- Original file, thumbnail, and video frames are removed from cloud storage where applicable.

## 10. Video Frame Extraction

Switch to `Video mode`, then use the `Upload Videos` panel:

1. Click `Choose videos`.
2. Select a short `.mp4` video.
3. Click `Upload videos`.

Expected result:

- The media card shows `media_type: video`.
- The card shows `Open original video`.
- The card shows `Extracted frames`.
- Extracted frame previews are displayed with copy buttons.
- The frame count should match roughly one extracted frame per second for the demo video duration. A 3-second video returns about 3 frame URLs; a 10-second video returns about 10.
- Each extracted frame is sent to the same GCP course ML model. A 3-second video with the same detected animal in all frames can therefore return a tag count such as `casuarius_casuarius x3`.

Supported video extensions include `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.3gp`, `.3g2`, `.wmv`, `.flv`, `.ts`, `.m2ts`, and `.ogv`, subject to ffmpeg codec support.

Use a short demo video. There is no hard 3-second rule, but the direct API upload path is intended for small coursework demo files; very large videos can exceed API Gateway/Lambda request limits.

## 11. GCP Mirror Check

After uploading media, run:

```bash
tools/google-cloud-sdk/bin/gcloud storage ls gs://aussie-ecolens-raywu361-mirror/media-metadata/
```

Expected result:

- Metadata JSON objects appear in the GCP bucket.
- This proves AWS processing mirrored metadata to the second cloud.

To inspect one object:

```bash
tools/google-cloud-sdk/bin/gcloud storage cat gs://aussie-ecolens-raywu361-mirror/media-metadata/OBJECT_NAME.json
```

Expected JSON fields include:

```json
{
  "filename": "...",
  "media_type": "image",
  "storage_url": "s3://...",
  "thumbnail_storage_url": "s3://...",
  "tags": {}
}
```

## 12. Notifications

In `Watch tags`, enter:

```text
casuarius_casuarius
```

Then enter an email address and click `Watch`.

Expected result:

- The status shows `Watch list updated`.
- Uploading a matching image or video creates a notification record.
- Click `Refresh notifications` in the UI.
- The Notifications panel shows at least one watched-tag notification.
- Calling `/api/notifications` also returns at least one notification for the watched tag.
- In-app notifications work without external email confirmation.
- In the deployed final configuration, SMTP email has been verified with Gmail App Password and the notification channels include `in_app`, `sns`, and `smtp`.

SNS email is configured, but the recipient must confirm the SNS subscription email before AWS can deliver messages to the inbox. To avoid depending on SNS confirmation during marking, the deployed project also supports SMTP through deployment variables:

```text
EMAIL_NOTIFICATION_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=...
SMTP_STARTTLS=true
```

Use a provider-specific app password, not a normal personal email password.

## 13. Correct Final State

The full project is working when:

- Cognito login succeeds.
- Batch upload shows one result card per file.
- Image uploads are tagged by the deployed course ML model.
- Duplicate upload is detected.
- Tag and species queries return matching media.
- Thumbnail lookup returns the full image URL.
- Query-by-file finds matching media without storing the query file.
- Manual tag add/remove works.
- Delete removes media from query results.
- Video upload returns extracted frame URLs and model-derived frame tags.
- GCP mirror bucket contains metadata JSON created from AWS uploads.
- Watched-tag notifications appear in the UI and through the in-app notification API; SMTP email delivery has been verified.
