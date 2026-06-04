#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DIR="${1:-${MODEL_SOURCE_DIR:-}}"
TARGET_DIR="${COURSE_MODEL_DIR:-$PROJECT_DIR/course_models}"

if [[ -z "$SOURCE_DIR" ]]; then
  cat >&2 <<'EOF'
Usage:
  scripts/prepare_course_models.sh /path/to/AussieEcoLense

The source directory must contain:
  model.pt
  mdv5a.pt
  labels.txt
  config.yaml
EOF
  exit 2
fi

required=(model.pt mdv5a.pt labels.txt config.yaml)
for name in "${required[@]}"; do
  if [[ ! -f "$SOURCE_DIR/$name" ]]; then
    echo "Missing required file: $SOURCE_DIR/$name" >&2
    exit 1
  fi
done

mkdir -p "$TARGET_DIR"
for name in "${required[@]}"; do
  cp "$SOURCE_DIR/$name" "$TARGET_DIR/$name"
done

echo "Course model assets copied to $TARGET_DIR"
du -sh "$TARGET_DIR"
