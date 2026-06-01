from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "assets" / "course" / "labels.txt"


def normalise_tag(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_label_aliases(path: Path = LABELS_PATH) -> Dict[str, List[str]]:
    aliases: Dict[str, List[str]] = {}
    if not path.exists():
        return aliases
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 7:
            continue
        _, _, _, _, genus, species, common = parts[:7]
        scientific = f"{genus}_{species}"
        canonical = normalise_tag(scientific)
        values = {canonical, normalise_tag(common), normalise_tag(genus), normalise_tag(species)}
        aliases[canonical] = sorted(value for value in values if value)
    return aliases


def tags_from_text(text: str, aliases: Dict[str, Iterable[str]] | None = None) -> Dict[str, int]:
    aliases = aliases or load_label_aliases()
    haystack = normalise_tag(text)
    tags: Dict[str, int] = {}
    for canonical, values in aliases.items():
        for alias in values:
            if alias and alias in haystack:
                tags[canonical] = tags.get(canonical, 0) + 1
                break
    return tags

