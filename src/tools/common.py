from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(slots=True)
class ToolArgumentError(ValueError):
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return self.message


def error_result(
    code: str,
    message: str,
    *,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    error: dict[str, Any] = {"code": code, "message": message}
    if field:
        error["field"] = field
    if details:
        error["details"] = details
    return json.dumps({"ok": False, "error": error}, indent=2)


def invalid_argument(message: str, *, field: str | None = None) -> ToolArgumentError:
    return ToolArgumentError(message=message, field=field)


def normalize_int(value: Any, *, field_name: str, min_value: int | None = None) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise invalid_argument(f"{field_name} must be an integer.", field=field_name) from exc
    if min_value is not None and normalized < min_value:
        raise invalid_argument(f"{field_name} must be >= {min_value}.", field=field_name)
    return normalized


def normalize_float(value: Any, *, field_name: str, min_value: float | None = None, max_value: float | None = None) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise invalid_argument(f"{field_name} must be a number.", field=field_name) from exc
    if min_value is not None and normalized < min_value:
        raise invalid_argument(f"{field_name} must be >= {min_value}.", field=field_name)
    if max_value is not None and normalized > max_value:
        raise invalid_argument(f"{field_name} must be <= {max_value}.", field=field_name)
    return normalized


def normalize_string_list(value: Any, *, field_name: str) -> list[str] | None:
    def _normalize_spaces(text: str) -> str:
        # Collapse mixed whitespace (including full-width space) to single ASCII spaces.
        return " ".join(text.replace("\u3000", " ").split())

    if value is None:
        return None
    if isinstance(value, str):
        raw = _normalize_spaces(value)
        if not raw:
            return None
        if "," in raw:
            parts = [_normalize_spaces(part) for part in raw.split(",") if _normalize_spaces(part)]
            return parts or None
        return [raw]
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize_spaces(str(item)) for item in value if _normalize_spaces(str(item))]
        return normalized or None
    raise invalid_argument(f"{field_name} must be a string or a list of strings.", field=field_name)


def normalize_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise invalid_argument(f"{field_name} must be a string.", field=field_name)
    normalized = value.strip()
    return normalized or None


def normalize_required_string(value: Any, *, field_name: str) -> str:
    normalized = normalize_optional_string(value, field_name=field_name)
    if not normalized:
        raise invalid_argument(f"{field_name} is required.", field=field_name)
    return normalized


def normalize_int_list(value: Any, *, field_name: str) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        raw = value.replace("\u3000", " ").strip()
        if not raw:
            return None
        parts = [part for part in re.split(r"[,\s]+", raw) if part]
        try:
            return [int(part) for part in parts]
        except ValueError as exc:
            raise invalid_argument(f"{field_name} must contain integers.", field=field_name) from exc
    if isinstance(value, (list, tuple, set)):
        try:
            normalized = [int(item) for item in value]
        except (TypeError, ValueError) as exc:
            raise invalid_argument(f"{field_name} must contain integers.", field=field_name) from exc
        return normalized or None
    raise invalid_argument(f"{field_name} must be an integer or a list of integers.", field=field_name)


def parse_published_after(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError as exc:
        raise invalid_argument(
            "published_after must use YYYY-MM-DD format (example: 2026-03-01).",
            field="published_after",
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)


def parse_timespan(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip().lower()
    if len(raw) < 2 or not raw[:-1].isdigit():
        raise invalid_argument("timespan must look like '72h', '7d', or '30m'.", field="timespan")
    amount = int(raw[:-1])
    unit = raw[-1]
    now = datetime.now(timezone.utc)
    if unit == "m":
        return now - timedelta(minutes=amount)
    if unit == "h":
        return now - timedelta(hours=amount)
    if unit == "d":
        return now - timedelta(days=amount)
    raise invalid_argument("timespan must use suffix m, h, or d.", field="timespan")
