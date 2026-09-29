"""Prompt and knowledge-pack text. The single-file build embeds them in EMBEDDED_ASSETS; development reads the files."""

from __future__ import annotations

import os
from typing import List

ASSET_DIR = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))


def asset(rel: str) -> str:
    embedded = globals().get("EMBEDDED_ASSETS")
    if isinstance(embedded, dict) and rel in embedded:
        return embedded[rel]
    try:
        with open(os.path.join(ASSET_DIR, rel), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def pack_text(names: List[str]) -> str:
    parts = [asset(f"packs/{name}.md").strip() for name in names]
    return "\n\n".join(part for part in parts if part)
