import json
from typing import Any

from ..store import list_sources_from_db


def _error_result(code: str, message: str, details: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return json.dumps(payload, indent=2)


async def list_sources(
    categories: list[str] | None = None,
    tiers: list[int] | None = None,
    limit: int = 100,
) -> str:
    """
    List available sources from the local source catalog.
    """
    try:
        rows = await list_sources_from_db(
            categories=categories,
            tiers=tiers,
            limit=limit,
        )
    except Exception as exc:
        return _error_result(
            "LIST_SOURCES_FAILED",
            "Error listing local source catalog.",
            {"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(rows),
            "sources": [
                {
                    "name": row.name,
                    "category": row.category,
                    "tier": row.tier,
                    "lang": row.lang,
                    "tags": row.tags,
                    "feed_url": row.feed_url,
                }
                for row in rows
            ],
        },
        indent=2,
    )
