"""Small shared helpers: ids, timestamps, response envelope."""
import secrets
from datetime import datetime, timezone

from flask import jsonify


def now_iso() -> str:
    """Current UTC time as ISO 8601 with milliseconds and a Z suffix (sorts correctly as text)."""
    return to_iso(datetime.now(timezone.utc))


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value) -> datetime | None:
    """Parse an ISO 8601 string. Naive values are treated as UTC. Returns None when invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def ok(data=None, status: int = 200):
    """Success envelope: { success: true, data }."""
    return jsonify({"success": True, "data": data}), status


def like_pattern(term: str) -> str:
    """Escape LIKE wildcards in user input so a search for '%' matches a literal percent sign."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
