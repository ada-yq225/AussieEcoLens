from __future__ import annotations

import cgi
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import time
import tempfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import unquote, urlparse

from PIL import Image

from .species import tags_from_text


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "var"
DB_PATH = DATA_DIR / "aussie_ecolens.sqlite3"
ORIGINALS = DATA_DIR / "storage" / "originals"
THUMBNAILS = DATA_DIR / "storage" / "thumbnails"
STATIC = ROOT / "web"
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
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".3g2", ".wmv", ".flv", ".ts", ".m2ts", ".ogv"}


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    THUMBNAILS.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT UNIQUE NOT NULL,
              first_name TEXT NOT NULL,
              last_name TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              created_at REAL NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS media (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              checksum TEXT UNIQUE NOT NULL,
              filename TEXT NOT NULL,
              media_type TEXT NOT NULL,
              original_path TEXT NOT NULL,
              thumbnail_path TEXT,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tags (
              media_id INTEGER NOT NULL,
              tag TEXT NOT NULL,
              count INTEGER NOT NULL,
              PRIMARY KEY(media_id, tag),
              FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS watchers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              email TEXT NOT NULL,
              tag TEXT NOT NULL,
              UNIQUE(user_id, email, tag)
            );
            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              email TEXT NOT NULL,
              tag TEXT NOT NULL,
              media_id INTEGER NOT NULL,
              message TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            """
        )


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def rel_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    try:
        return "/" + p.relative_to(ROOT).as_posix()
    except ValueError:
        return "/" + p.as_posix().lstrip("/")


def media_response(row: sqlite3.Row, tags: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    item = {
        "id": row["id"],
        "checksum": row["checksum"],
        "filename": row["filename"],
        "media_type": row["media_type"],
        "full_url": rel_url(row["original_path"]),
        "thumbnail_url": rel_url(row["thumbnail_path"]) if row["thumbnail_path"] else None,
        "created_at": row["created_at"],
    }
    item["tags"] = tags if tags is not None else get_tags(row["id"])
    return item


def get_tags(media_id: int) -> Dict[str, int]:
    with db() as conn:
        rows = conn.execute("SELECT tag, count FROM tags WHERE media_id = ?", (media_id,)).fetchall()
    return {row["tag"]: row["count"] for row in rows}


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_tags(filename: str, data: bytes) -> Dict[str, int]:
    """Deterministic local demo tagger.

    Production should replace this with the provided ML model. For local tests, filenames
    such as koala2_wombat1.jpg become {"koala": 2, "wombat": 1}.
    """
    if os.environ.get("LOCAL_TAGGER_MODE") == "course":
        tags = course_model_tags(filename, data)
        if tags:
            return tags

    lower = filename.lower()
    tags: Dict[str, int] = tags_from_text(filename)
    for species in SPECIES:
        match = re.search(rf"{species}[_-]?(\d+)?", lower)
        if match:
            tags[species] = int(match.group(1) or "1")
    if not tags:
        digest = checksum_bytes(data)
        picked = sorted(SPECIES)[int(digest[:2], 16) % len(SPECIES)]
        tags[picked] = 1
    return tags


def course_model_tags(filename: str, data: bytes) -> Dict[str, int]:
    python_path = ROOT / ".venv312" / "bin" / "python"
    script_path = ROOT / "scripts" / "course_model_predict.py"
    model_path = Path(os.environ.get("COURSE_MODEL_PATH", str(ROOT / "course_models" / "model.pt")))
    detector_path = Path(os.environ.get("COURSE_DETECTOR_PATH", str(ROOT / "course_models" / "mdv5a.pt")))
    if not python_path.exists() or not script_path.exists() or not model_path.exists() or not detector_path.exists():
        return {}
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.TemporaryDirectory() as tmp:
        image_path = Path(tmp) / f"upload{suffix}"
        output_path = Path(tmp) / "prediction.json"
        image_path.write_bytes(data)
        try:
            subprocess.run(
                [
                    str(python_path),
                    str(script_path),
                    str(image_path),
                    "--model",
                    str(model_path),
                    "--detector",
                    str(detector_path),
                    "--output",
                    str(output_path),
                ],
                cwd=str(ROOT),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=90,
            )
        except Exception:
            return {}
        if not output_path.exists():
            return {}
        result = json.loads(output_path.read_text(encoding="utf-8"))
    tags: Dict[str, int] = {}
    for prediction in result.get("predictions", []):
        species = prediction.get("species")
        if species:
            tag = species.lower()
            tags[tag] = tags.get(tag, 0) + 1
    return tags


def media_type_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_TYPES:
        return "image"
    if ext in VIDEO_TYPES:
        return "video"
    return "unknown"


def create_thumbnail(source: Path, checksum: str) -> Optional[Path]:
    try:
        with Image.open(source) as image:
            image.thumbnail((320, 320))
            target = THUMBNAILS / f"{checksum}.jpg"
            image.convert("RGB").save(target, "JPEG", quality=82, optimize=True)
            return target
    except Exception:
        return None


def insert_media(filename: str, data: bytes) -> Tuple[Dict[str, Any], bool]:
    checksum = checksum_bytes(data)
    with db() as conn:
        existing = conn.execute("SELECT * FROM media WHERE checksum = ?", (checksum,)).fetchone()
        if existing:
            return media_response(existing), True

    ext = Path(filename).suffix.lower() or ".bin"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    original = ORIGINALS / f"{checksum}_{safe_name}"
    original.write_bytes(data)
    kind = media_type_for(filename)
    thumbnail = create_thumbnail(original, checksum) if kind == "image" else None
    tags = detect_tags(filename, data)

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO media(checksum, filename, media_type, original_path, thumbnail_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (checksum, filename, kind, str(original), str(thumbnail) if thumbnail else None, time.time()),
        )
        media_id = cur.lastrowid
        for tag, count in tags.items():
            conn.execute(
                "INSERT INTO tags(media_id, tag, count) VALUES (?, ?, ?)",
                (media_id, tag, count),
            )
        notify_watchers(conn, media_id, tags.keys())
        row = conn.execute("SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
    return media_response(row, tags), False


def notify_watchers(conn: sqlite3.Connection, media_id: int, tags: Iterable[str]) -> None:
    for tag in tags:
        watchers = conn.execute("SELECT * FROM watchers WHERE tag = ?", (tag,)).fetchall()
        for watcher in watchers:
            conn.execute(
                """
                INSERT INTO notifications(user_id, email, tag, media_id, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    watcher["user_id"],
                    watcher["email"],
                    tag,
                    media_id,
                    f"New or updated media matched watched tag: {tag}",
                    time.time(),
                ),
            )


def find_media_by_url(conn: sqlite3.Connection, url: str) -> Optional[sqlite3.Row]:
    parsed = unquote(urlparse(url).path if "://" in url else url)
    path = str((ROOT / parsed.lstrip("/")).resolve())
    return conn.execute(
        "SELECT * FROM media WHERE original_path = ? OR thumbnail_path = ?",
        (path, path),
    ).fetchone()


class Handler(SimpleHTTPRequestHandler):
    server_version = "AussieEcoLens/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/me":
            user = self.require_user()
            if not user:
                return
            self.send_json({"user": dict(user)})
            return
        if parsed.path == "/api/notifications":
            user = self.require_user()
            if not user:
                return
            with db() as conn:
                rows = conn.execute(
                    "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
                    (user["id"],),
                ).fetchall()
            self.send_json({"notifications": [dict(row) for row in rows]})
            return
        if parsed.path.startswith("/var/storage/"):
            self.serve_file(ROOT / parsed.path.lstrip("/"))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        public = {"/api/auth/signup", "/api/auth/signin"}
        user = None if parsed.path in public else self.require_user()
        if parsed.path not in public and not user:
            return

        routes = {
            "/api/auth/signup": self.signup,
            "/api/auth/signin": self.signin,
            "/api/auth/signout": self.signout,
            "/api/upload": self.upload,
            "/api/query/tags": self.query_tags,
            "/api/query/species": self.query_species,
            "/api/query/thumbnail": self.query_thumbnail,
            "/api/query/file": self.query_file,
            "/api/tags/edit": self.edit_tags,
            "/api/delete": self.delete_media,
            "/api/notifications/watch": self.watch_tags,
        }
        route = routes.get(parsed.path)
        if not route:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        route(user)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def read_multipart_file(self) -> Tuple[str, bytes]:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("content-type"),
            },
        )
        field = form["file"] if "file" in form else None
        if field is None or not getattr(field, "filename", None):
            raise ValueError("missing file")
        return field.filename, field.file.read()

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        target = STATIC / ("index.html" if path in {"", "/"} else path.lstrip("/"))
        self.serve_file(target)

    def serve_file(self, target: Path) -> None:
        try:
            resolved = target.resolve()
            if not (str(resolved).startswith(str(STATIC.resolve())) or str(resolved).startswith(str(DATA_DIR.resolve()))):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", mimetypes.guess_type(str(resolved))[0] or "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)

    def current_user(self) -> Optional[sqlite3.Row]:
        auth = self.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth.split(" ", 1)[1].strip()
        with db() as conn:
            return conn.execute(
                """
                SELECT users.id, users.email, users.first_name, users.last_name
                FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

    def require_user(self) -> Optional[sqlite3.Row]:
        user = self.current_user()
        if not user:
            self.send_json({"error": "authentication required"}, HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def signup(self, _: Optional[sqlite3.Row]) -> None:
        payload = self.read_json()
        required = ["email", "first_name", "last_name", "password"]
        if any(not payload.get(key) for key in required):
            self.send_json({"error": "email, first_name, last_name, and password are required"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO users(email, first_name, last_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        payload["email"].lower(),
                        payload["first_name"],
                        payload["last_name"],
                        password_hash(payload["password"]),
                        time.time(),
                    ),
                )
            self.send_json({"ok": True, "message": "Local demo user created. Cognito email verification is required in cloud."})
        except sqlite3.IntegrityError:
            self.send_json({"error": "email already exists"}, HTTPStatus.CONFLICT)

    def signin(self, _: Optional[sqlite3.Row]) -> None:
        payload = self.read_json()
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (payload.get("email", "").lower(),)).fetchone()
            if not user or user["password_hash"] != password_hash(payload.get("password", "")):
                self.send_json({"error": "invalid credentials"}, HTTPStatus.UNAUTHORIZED)
                return
            token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO sessions(token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], time.time()))
        self.send_json({"token": token, "user": {"email": user["email"], "first_name": user["first_name"], "last_name": user["last_name"]}})

    def signout(self, _: Optional[sqlite3.Row]) -> None:
        auth = self.headers.get("authorization", "")
        token = auth.split(" ", 1)[1].strip() if " " in auth else ""
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self.send_json({"ok": True})

    def upload(self, _: sqlite3.Row) -> None:
        try:
            filename, data = self.read_multipart_file()
            item, duplicate = insert_media(filename, data)
            self.send_json({"duplicate": duplicate, "media": item})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def query_tags(self, _: sqlite3.Row) -> None:
        payload = self.read_json()
        tags = payload.get("tags", payload)
        if isinstance(tags, list):
            tags = {tag: 1 for tag in tags}
        self.send_json({"results": search_by_tags({str(k): int(v) for k, v in tags.items()})})

    def query_species(self, _: sqlite3.Row) -> None:
        payload = self.read_json()
        species = payload.get("species") or payload.get("tag")
        if not species:
            self.send_json({"error": "species is required"}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"results": search_by_tags({species: 1})})

    def query_thumbnail(self, _: sqlite3.Row) -> None:
        payload = self.read_json()
        with db() as conn:
            row = find_media_by_url(conn, payload.get("thumbnail_url", ""))
            if not row:
                self.send_json({"error": "thumbnail not found"}, HTTPStatus.NOT_FOUND)
                return
        self.send_json({"full_url": rel_url(row["original_path"])})

    def query_file(self, _: sqlite3.Row) -> None:
        try:
            filename, data = self.read_multipart_file()
            tags = detect_tags(filename, data)
            self.send_json({"detected_tags": tags, "results": search_by_tags({tag: 1 for tag in tags})})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def edit_tags(self, _: sqlite3.Row) -> None:
        payload = self.read_json()
        urls = payload.get("urls", [])
        raw_tags = payload.get("tags", [])
        operation = int(payload.get("operation", 1))
        tags = raw_tags if isinstance(raw_tags, dict) else {tag: 1 for tag in raw_tags}
        updated = []
        with db() as conn:
            for url in urls:
                row = find_media_by_url(conn, url)
                if not row:
                    continue
                for tag, count in tags.items():
                    if operation == 1:
                        conn.execute(
                            """
                            INSERT INTO tags(media_id, tag, count) VALUES (?, ?, ?)
                            ON CONFLICT(media_id, tag) DO UPDATE SET count = count + excluded.count
                            """,
                            (row["id"], str(tag), int(count)),
                        )
                        notify_watchers(conn, row["id"], [str(tag)])
                    else:
                        conn.execute("DELETE FROM tags WHERE media_id = ? AND tag = ?", (row["id"], str(tag)))
                updated.append(media_response(row))
        self.send_json({"updated": updated})

    def delete_media(self, _: sqlite3.Row) -> None:
        payload = self.read_json()
        deleted = []
        with db() as conn:
            for url in payload.get("urls", []):
                row = find_media_by_url(conn, url)
                if not row:
                    continue
                for key in ("original_path", "thumbnail_path"):
                    if row[key]:
                        try:
                            Path(row[key]).unlink(missing_ok=True)
                        except OSError:
                            pass
                conn.execute("DELETE FROM tags WHERE media_id = ?", (row["id"],))
                conn.execute("DELETE FROM media WHERE id = ?", (row["id"],))
                deleted.append(row["id"])
        self.send_json({"deleted": deleted})

    def watch_tags(self, user: sqlite3.Row) -> None:
        payload = self.read_json()
        tags = payload.get("tags", [])
        email = payload.get("email") or user["email"]
        with db() as conn:
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO watchers(user_id, email, tag) VALUES (?, ?, ?)",
                    (user["id"], email, str(tag)),
                )
        self.send_json({"ok": True})


def search_by_tags(required: Dict[str, int]) -> list[Dict[str, Any]]:
    if not required:
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM media ORDER BY created_at DESC").fetchall()
        results = []
        for row in rows:
            tags = get_tags(row["id"])
            if all(tags.get(tag, 0) >= count for tag, count in required.items()):
                results.append(media_response(row, tags))
    return results


def reset_demo_data() -> None:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    init_db()


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    init_db()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Aussie EcoLens local demo running at http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080")))
