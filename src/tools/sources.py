import json
from typing import Any

from ..store import (
    list_source_categories_from_db,
    list_source_names_from_db,
    list_source_tiers_from_db,
    list_sources_from_db,
)
from .common import ToolArgumentError, error_result, normalize_int, normalize_int_list, normalize_string_list


async def list_sources(
    categories: Any | None = None,
    tiers: Any | None = None,
    limit: Any = 100,
    offset: Any = 0,
) -> str:
    """
    List available sources from the local source catalog.
    """
    try:
        normalized_categories = normalize_string_list(categories, field_name="categories")
        normalized_tiers = normalize_int_list(tiers, field_name="tiers")
        normalized_limit = normalize_int(limit, field_name="limit", min_value=1)
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)

        rows = await list_sources_from_db(
            categories=normalized_categories,
            tiers=normalized_tiers,
            limit=normalized_limit,
            offset=normalized_offset,
        )
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except Exception as exc:
        return error_result(
            "LIST_SOURCES_FAILED",
            "Error listing local source catalog.",
            details={"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(rows),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": normalized_offset + len(rows),
            },
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


async def list_categories(limit: Any = 200, offset: Any = 0) -> str:
    """
    List all available source categories.
    """
    try:
        normalized_limit = normalize_int(limit, field_name="limit", min_value=1)
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        categories = await list_source_categories_from_db(limit=normalized_limit, offset=normalized_offset)
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except Exception as exc:
        return error_result(
            "LIST_CATEGORIES_FAILED",
            "Error listing source categories.",
            details={"reason": str(exc)},
        )
    return json.dumps(
        {
            "ok": True,
            "count": len(categories),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": normalized_offset + len(categories),
            },
            "categories": categories,
        },
        indent=2,
    )


async def list_tiers(limit: Any = 20, offset: Any = 0) -> str:
    """
    List all available source tiers.
    """
    try:
        normalized_limit = normalize_int(limit, field_name="limit", min_value=1)
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        tiers = await list_source_tiers_from_db(limit=normalized_limit, offset=normalized_offset)
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except Exception as exc:
        return error_result(
            "LIST_TIERS_FAILED",
            "Error listing source tiers.",
            details={"reason": str(exc)},
        )
    return json.dumps(
        {
            "ok": True,
            "count": len(tiers),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": normalized_offset + len(tiers),
            },
            "tiers": tiers,
        },
        indent=2,
    )


async def list_source_names(
    categories: Any | None = None,
    tiers: Any | None = None,
    limit: Any = 200,
    offset: Any = 0,
) -> str:
    """
    List source names and optional category/tier filters.
    """
    try:
        normalized_categories = normalize_string_list(categories, field_name="categories")
        normalized_tiers = normalize_int_list(tiers, field_name="tiers")
        normalized_limit = normalize_int(limit, field_name="limit", min_value=1)
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        names = await list_source_names_from_db(
            categories=normalized_categories,
            tiers=normalized_tiers,
            limit=normalized_limit,
            offset=normalized_offset,
        )
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except Exception as exc:
        return error_result(
            "LIST_SOURCE_NAMES_FAILED",
            "Error listing source names.",
            details={"reason": str(exc)},
        )
    return json.dumps(
        {
            "ok": True,
            "count": len(names),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": normalized_offset + len(names),
            },
            "source_names": names,
        },
        indent=2,
    )
