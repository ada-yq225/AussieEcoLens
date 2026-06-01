from __future__ import annotations

import base64
import cgi
import hashlib
import io
import json
import mimetypes
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Optional, Tuple

import boto3
from PIL import Image


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
rekognition = boto3.client("rekognition")

MEDIA_BUCKET = os.environ["MEDIA_BUCKET"]
THUMBNAIL_BUCKET = os.environ["THUMBNAIL_BUCKET"]
MEDIA_TABLE = os.environ["MEDIA_TABLE"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
TAGGER_MODE = os.environ.get("TAGGER_MODE", "filename")
GCP_MIRROR_ENDPOINT = os.environ.get("GCP_MIRROR_ENDPOINT", "")
GCP_SHARED_SECRET = os.environ.get("GCP_SHARED_SECRET", "")
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "/opt/bin/ffmpeg")
SPECIES = {
    "koala",
    "wombat",
    "magpie",
    "dingo",
    "kangaroo",
    "platypus",
    "emu",
    "cassowary",
    "possum",
}
COURSE_ALIASES = {
    "alectura_lathami": ["alectura_lathami", "australian_brushturkey"],
    "bos_taurus": ["bos_taurus", "cattle"],
    "canis_familiaris": ["canis_familiaris", "domestic_dog"],
    "canis_dingo": ["canis_dingo", "dingo"],
    "casuarius_casuarius": ["casuarius_casuarius", "southern_cassowary"],
    "felis_catus": ["felis_catus", "domestic_cat"],
    "heteromyias_cinereifrons": ["heteromyias_cinereifrons", "grey_headed_robin"],
    "hypsiprymnodon_moschatus": ["hypsiprymnodon_moschatus", "musky_rat_kangaroo"],
    "megapodius_reinwardt": ["megapodius_reinwardt", "orange_footed_scrubfowl"],
    "orthonyx_spaldingii": ["orthonyx_spaldingii", "northern_chowchilla"],
    "perameles_nasuta": ["perameles_nasuta", "long_nosed_bandicoot"],
    "sus_scrofa": ["sus_scrofa", "wild_boar"],
    "thylogale_stigmatica": ["thylogale_stigmatica", "red_legged_pademelon"],
    "uromys_caudimaculatus": ["uromys_caudimaculatus", "giant_white_tailed_rat"],
}
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def table():
    return dynamodb.Table(MEDIA_TABLE)


def response(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-headers": "authorization,content-type",
            "access-control-allow-methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(payload),
    }


def user_id(event: Dict[str, Any]) -> str:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    return claims.get("sub") or "anonymous"


def user_email(event: Dict[str, Any]) -> str:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    return claims.get("email") or ""


def body_bytes(event: Dict[str, Any]) -> bytes:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(raw)
    return raw.encode("utf-8")


def parse_json(event: Dict[str, Any]) -> Dict[str, Any]:
    data = body_bytes(event)
    return json.loads(data.decode("utf-8")) if data else {}


def parse_upload(event: Dict[str, Any]) -> Tuple[str, bytes, str]:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body_bytes(event))),
        }
        form = cgi.FieldStorage(fp=io.BytesIO(body_bytes(event)), headers=headers, environ=environ)
        field = form["file"] if "file" in form else None
        if field is None or not getattr(field, "filename", None):
            raise ValueError("missing file field")
        data = field.file.read()
        return field.filename, data, field.type or "application/octet-stream"

    payload = parse_json(event)
    filename = payload.get("filename")
    encoded = payload.get("content_base64")
    if not filename or not encoded:
        raise ValueError("filename and content_base64 are required")
    return filename, base64.b64decode(encoded), payload.get("content_type") or "application/octet-stream"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename))


def media_type_for(filename: str, content_type: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in IMAGE_TYPES or content_type.startswith("image/"):
        return "image"
    if ext in VIDEO_TYPES or content_type.startswith("video/"):
        return "video"
    return "unknown"


def filename_tags(filename: str, data: bytes) -> Dict[str, int]:
    lower = filename.lower()
    tags: Dict[str, int] = {}
    normalised = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")
    for canonical, aliases in COURSE_ALIASES.items():
        if any(alias in normalised for alias in aliases):
            tags[canonical] = tags.get(canonical, 0) + 1
    for species in SPECIES:
        match = re.search(rf"{species}[_-]?(\d+)?", lower)
        if match:
            tags[species] = int(match.group(1) or "1")
    if not tags:
        digest = sha256(data)
        picked = sorted(SPECIES)[int(digest[:2], 16) % len(SPECIES)]
        tags[picked] = 1
    return tags


def rekognition_tags(data: bytes) -> Dict[str, int]:
    result = rekognition.detect_labels(Image={"Bytes": data}, MaxLabels=20, MinConfidence=65)
    tags: Dict[str, int] = {}
    for label in result.get("Labels", []):
        name = label.get("Name", "").lower()
        if name in SPECIES:
            tags[name] = max(1, len(label.get("Instances") or [1]))
    return tags


def extract_video_frames(data: bytes, checksum: str) -> list[Tuple[str, bytes]]:
    if not os.path.exists(FFMPEG_PATH):
        return []
    source = f"/tmp/video-{sha256(data)}"
    frames_dir = f"/tmp/frames-{int(time.time() * 1000)}"
    os.makedirs(frames_dir, exist_ok=True)
    with open(source, "wb") as handle:
        handle.write(data)
    subprocess.run(
        [
            FFMPEG_PATH,
            "-y",
            "-i",
            source,
            "-vf",
            "fps=1",
            os.path.join(frames_dir, "frame-%04d.jpg"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
    )
    frames = []
    for filename in sorted(os.listdir(frames_dir)):
        if not filename.endswith(".jpg"):
            continue
        with open(os.path.join(frames_dir, filename), "rb") as handle:
            frame_data = handle.read()
        key = f"video-frames/{checksum}/{filename}"
        s3.put_object(Bucket=THUMBNAIL_BUCKET, Key=key, Body=frame_data, ContentType="image/jpeg")
        frames.append((key, frame_data))
    return frames


def video_frame_tags(frames: list[Tuple[str, bytes]]) -> Dict[str, int]:
    combined: Dict[str, int] = {}
    for _, frame_data in frames:
        frame_tags = rekognition_tags(frame_data) if TAGGER_MODE == "rekognition" else {}
        for tag, count in frame_tags.items():
            combined[tag] = combined.get(tag, 0) + count
    return combined


def detect_tags(filename: str, data: bytes, media_type: str, frames: Optional[list[Tuple[str, bytes]]] = None) -> Dict[str, int]:
    if media_type == "image" and TAGGER_MODE == "rekognition":
        tags = rekognition_tags(data)
        if tags:
            return tags
    if media_type == "video":
        tags = video_frame_tags(frames or [])
        if tags:
            return tags
    return filename_tags(filename, data)


def create_thumbnail(data: bytes, checksum: str) -> Optional[str]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((320, 320))
            out = io.BytesIO()
            image.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
            key = f"thumbnails/{checksum}.jpg"
            s3.put_object(
                Bucket=THUMBNAIL_BUCKET,
                Key=key,
                Body=out.getvalue(),
                ContentType="image/jpeg",
            )
            return key
    except Exception:
        return None


def canonical_url(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def signed_url(bucket: str, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )


def media_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    original_key = item["original_key"]
    thumbnail_key = item.get("thumbnail_key")
    frame_keys = item.get("frame_keys") or []
    return {
        "id": item["checksum"],
        "checksum": item["checksum"],
        "filename": item["filename"],
        "media_type": item["media_type"],
        "storage_url": canonical_url(MEDIA_BUCKET, original_key),
        "thumbnail_storage_url": canonical_url(THUMBNAIL_BUCKET, thumbnail_key) if thumbnail_key else None,
        "full_url": signed_url(MEDIA_BUCKET, original_key),
        "thumbnail_url": signed_url(THUMBNAIL_BUCKET, thumbnail_key) if thumbnail_key else None,
        "frame_urls": [signed_url(THUMBNAIL_BUCKET, key) for key in frame_keys],
        "frame_storage_urls": [canonical_url(THUMBNAIL_BUCKET, key) for key in frame_keys],
        "tags": {k: int(v) for k, v in item.get("tags", {}).items()},
        "created_at": float(item.get("created_at", 0)),
    }


def put_media(filename: str, data: bytes, content_type: str, owner: str) -> Tuple[Dict[str, Any], bool]:
    checksum = sha256(data)
    key = f"originals/{checksum}_{safe_filename(filename)}"
    media_type = media_type_for(filename, content_type)
    tbl = table()
    existing = tbl.get_item(Key={"pk": f"MEDIA#{checksum}"}).get("Item")
    if existing:
        return media_payload(existing), True

    s3.put_object(
        Bucket=MEDIA_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
    )
    thumbnail_key = create_thumbnail(data, checksum) if media_type == "image" else None
    frames = extract_video_frames(data, checksum) if media_type == "video" else []
    frame_keys = [key for key, _ in frames]
    tags = detect_tags(filename, data, media_type, frames)
    item = {
        "pk": f"MEDIA#{checksum}",
        "kind": "MEDIA",
        "checksum": checksum,
        "filename": filename,
        "media_type": media_type,
        "original_key": key,
        "thumbnail_key": thumbnail_key or "",
        "frame_keys": frame_keys,
        "tags": tags,
        "owner": owner,
        "created_at": time.time(),
    }
    tbl.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
    notify_watchers(tags.keys(), item)
    mirror_to_gcp(item)
    return media_payload(item), False


def mirror_to_gcp(media_item: Dict[str, Any]) -> None:
    if not GCP_MIRROR_ENDPOINT:
        return
    payload = json.dumps(
        {
            "checksum": media_item["checksum"],
            "filename": media_item["filename"],
            "media_type": media_item["media_type"],
            "storage_url": canonical_url(MEDIA_BUCKET, media_item["original_key"]),
            "thumbnail_storage_url": canonical_url(THUMBNAIL_BUCKET, media_item["thumbnail_key"])
            if media_item.get("thumbnail_key")
            else None,
            "tags": media_item.get("tags", {}),
            "created_at": media_item.get("created_at"),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        GCP_MIRROR_ENDPOINT,
        data=payload,
        headers={"content-type": "application/json", "x-aussie-ecolens-secret": GCP_SHARED_SECRET},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as res:
        res.read()


def notify_watchers(tags: Iterable[str], media_item: Dict[str, Any]) -> None:
    tbl = table()
    for tag in tags:
        scan = tbl.scan(
            FilterExpression="#kind = :kind AND #tag = :tag",
            ExpressionAttributeNames={"#kind": "kind", "#tag": "tag"},
            ExpressionAttributeValues={":kind": "WATCH", ":tag": tag},
        )
        for watcher in scan.get("Items", []):
            message = {
                "email": watcher["email"],
                "tag": tag,
                "filename": media_item["filename"],
                "checksum": media_item["checksum"],
            }
            sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=f"Aussie EcoLens tag matched: {tag}", Message=json.dumps(message))
            tbl.put_item(
                Item={
                    "pk": f"NOTE#{watcher['user_id']}#{int(time.time() * 1000)}",
                    "kind": "NOTE",
                    "user_id": watcher["user_id"],
                    "email": watcher["email"],
                    "tag": tag,
                    "media_checksum": media_item["checksum"],
                    "message": f"New or updated media matched watched tag: {tag}",
                    "created_at": time.time(),
                }
            )


def all_media() -> list[Dict[str, Any]]:
    scan = table().scan(
        FilterExpression="#kind = :kind",
        ExpressionAttributeNames={"#kind": "kind"},
        ExpressionAttributeValues={":kind": "MEDIA"},
    )
    return scan.get("Items", [])


def search_by_tags(required: Dict[str, int]) -> list[Dict[str, Any]]:
    results = []
    for item in all_media():
        tags = {k: int(v) for k, v in item.get("tags", {}).items()}
        if all(tags.get(tag, 0) >= int(count) for tag, count in required.items()):
            results.append(media_payload(item))
    return sorted(results, key=lambda row: row["created_at"], reverse=True)


def key_from_url(url: str, expected_bucket: Optional[str] = None) -> Optional[Tuple[str, str]]:
    if url.startswith("s3://"):
        rest = url[5:]
        bucket, key = rest.split("/", 1)
        return bucket, key
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path).lstrip("/")
    host = parsed.netloc
    if ".s3." in host or ".s3-" in host or host.endswith(".amazonaws.com"):
        bucket = host.split(".s3")[0]
        return bucket, path
    if expected_bucket:
        return expected_bucket, path
    return None


def media_from_url(url: str) -> Optional[Dict[str, Any]]:
    parsed = key_from_url(url)
    if not parsed:
        return None
    bucket, key = parsed
    for item in all_media():
        if (bucket == MEDIA_BUCKET and item.get("original_key") == key) or (
            bucket == THUMBNAIL_BUCKET and item.get("thumbnail_key") == key
        ):
            return item
    return None


def upload(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    processed = 0
    if event.get("source") == "aws.s3" and event.get("detail"):
        detail = event["detail"]
        bucket = detail["bucket"]["name"]
        key = urllib.parse.unquote_plus(detail["object"]["key"])
        if bucket == MEDIA_BUCKET:
            obj = s3.get_object(Bucket=bucket, Key=key)
            filename = os.path.basename(key)
            put_media(filename, obj["Body"].read(), obj.get("ContentType") or "application/octet-stream", "s3-event")
            processed += 1
        return response(200, {"ok": True, "records": processed})

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        if bucket != MEDIA_BUCKET:
            continue
        obj = s3.get_object(Bucket=bucket, Key=key)
        filename = os.path.basename(key)
        put_media(filename, obj["Body"].read(), obj.get("ContentType") or "application/octet-stream", "s3-event")
        processed += 1
    return response(200, {"ok": True, "records": processed})


def api(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(200, {"ok": True})

    route = event.get("rawPath") or event.get("path") or "/"
    try:
        if route == "/api/upload":
            filename, data, content_type = parse_upload(event)
            media, duplicate = put_media(filename, data, content_type, user_id(event))
            return response(200, {"duplicate": duplicate, "media": media})

        if route == "/api/query/tags":
            payload = parse_json(event)
            tags = payload.get("tags", payload)
            if isinstance(tags, list):
                tags = {tag: 1 for tag in tags}
            return response(200, {"results": search_by_tags({str(k): int(v) for k, v in tags.items()})})

        if route == "/api/query/species":
            payload = parse_json(event)
            species = payload.get("species") or payload.get("tag")
            return response(200, {"results": search_by_tags({str(species): 1})})

        if route == "/api/query/thumbnail":
            payload = parse_json(event)
            item = media_from_url(payload.get("thumbnail_url", ""))
            if not item:
                return response(404, {"error": "thumbnail not found"})
            return response(200, {"full_url": signed_url(MEDIA_BUCKET, item["original_key"])})

        if route == "/api/query/file":
            filename, data, content_type = parse_upload(event)
            media_type = media_type_for(filename, content_type)
            tags = detect_tags(filename, data, media_type)
            return response(200, {"detected_tags": tags, "results": search_by_tags({tag: 1 for tag in tags})})

        if route == "/api/tags/edit":
            payload = parse_json(event)
            tags = payload.get("tags", [])
            tags = tags if isinstance(tags, dict) else {tag: 1 for tag in tags}
            operation = int(payload.get("operation", 1))
            updated = []
            tbl = table()
            for url in payload.get("urls", []):
                item = media_from_url(url)
                if not item:
                    continue
                item_tags = {k: int(v) for k, v in item.get("tags", {}).items()}
                for tag, count in tags.items():
                    if operation == 1:
                        item_tags[str(tag)] = item_tags.get(str(tag), 0) + int(count)
                    else:
                        item_tags.pop(str(tag), None)
                item["tags"] = item_tags
                tbl.put_item(Item=item)
                if operation == 1:
                    notify_watchers(tags.keys(), item)
                updated.append(media_payload(item))
            return response(200, {"updated": updated})

        if route == "/api/delete":
            payload = parse_json(event)
            deleted = []
            tbl = table()
            for url in payload.get("urls", []):
                item = media_from_url(url)
                if not item:
                    continue
                s3.delete_object(Bucket=MEDIA_BUCKET, Key=item["original_key"])
                if item.get("thumbnail_key"):
                    s3.delete_object(Bucket=THUMBNAIL_BUCKET, Key=item["thumbnail_key"])
                for frame_key in item.get("frame_keys", []):
                    s3.delete_object(Bucket=THUMBNAIL_BUCKET, Key=frame_key)
                tbl.delete_item(Key={"pk": item["pk"]})
                deleted.append(item["checksum"])
            return response(200, {"deleted": deleted})

        if route == "/api/notifications/watch":
            payload = parse_json(event)
            email = payload.get("email") or user_email(event)
            if not email:
                return response(400, {"error": "email is required"})
            for tag in payload.get("tags", []):
                table().put_item(
                    Item={
                        "pk": f"WATCH#{user_id(event)}#{email}#{tag}",
                        "kind": "WATCH",
                        "user_id": user_id(event),
                        "email": email,
                        "tag": str(tag),
                        "created_at": time.time(),
                    }
                )
            return response(200, {"ok": True})

        if route == "/api/notifications":
            scan = table().scan(
                FilterExpression="#kind = :kind AND user_id = :user_id",
                ExpressionAttributeNames={"#kind": "kind"},
                ExpressionAttributeValues={":kind": "NOTE", ":user_id": user_id(event)},
            )
            return response(200, {"notifications": scan.get("Items", [])})

        return response(404, {"error": "not found", "route": route})
    except Exception as exc:
        return response(400, {"error": str(exc), "route": route})
