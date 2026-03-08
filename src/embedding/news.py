from __future__ import annotations

from typing import Any


def build_news_embedding_text(payload: dict[str, Any]) -> str:
    tags = ", ".join(str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip())
    parts = [
        f"title: {str(payload.get('title') or '').strip()}",
        f"source: {str(payload.get('name') or '').strip()}",
        f"category: {str(payload.get('category') or '').strip()}",
        f"tier: {str(payload.get('tier') or '').strip()}",
        f"domain: {str(payload.get('domain') or '').strip()}",
    ]
    if tags:
        parts.append(f"tags: {tags}")
    return "\n".join(part for part in parts if part.split(': ', 1)[1])
