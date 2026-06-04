#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
PACKAGE_NAME="${PACKAGE_NAME:-AussieEcoLens_submission.zip}"
PACKAGE_PATH="$DIST_DIR/$PACKAGE_NAME"
STAGING_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$DIST_DIR"

git -C "$PROJECT_DIR" archive --format=tar HEAD | tar -x -C "$STAGING_DIR"

if [[ -f "$PROJECT_DIR/course_models/model.pt" && -f "$PROJECT_DIR/course_models/mdv5a.pt" ]]; then
  mkdir -p "$STAGING_DIR/course_models"
  cp "$PROJECT_DIR/course_models"/model.pt "$STAGING_DIR/course_models/"
  cp "$PROJECT_DIR/course_models"/mdv5a.pt "$STAGING_DIR/course_models/"
  for optional in labels.txt config.yaml README.md; do
    if [[ -f "$PROJECT_DIR/course_models/$optional" ]]; then
      cp "$PROJECT_DIR/course_models/$optional" "$STAGING_DIR/course_models/"
    fi
  done
else
  echo "Warning: course_models/model.pt or course_models/mdv5a.pt is missing." >&2
  echo "The zip will be usable for local CI but not for offline course-model inference." >&2
fi

find "$STAGING_DIR" -name '.DS_Store' -delete

rm -f "$PACKAGE_PATH"
(cd "$STAGING_DIR" && zip -qr "$PACKAGE_PATH" .)

echo "Created $PACKAGE_PATH"
du -sh "$PACKAGE_PATH"
