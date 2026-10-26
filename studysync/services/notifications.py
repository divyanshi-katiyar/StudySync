from datetime import datetime, timedelta, timezone

from flask import request

from ..db import all_rows, get_db, one
from ..errors import ApiError
from ..serializers import GROUP_SQL, SESSION_SQL, group_json, notification_json, session_json
from ..utils import now_iso, to_iso
from ..validation import int_arg


def list_notifications(user_id: str) -> list:
    limit = int_arg("limit", 50, 1, 100)
    unread_only = request.args.get("unread", "").lower() in ("1", "true")
    clause = " AND is_read = 0" if unread_only else ""
    rows = all_rows(f"SELECT * FROM notifications WHERE user_id = ?{clause} ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    return [notification_json(r) for r in rows]


def mark_read(notification_id: str, user_id: str) -> dict:
    row = one("SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notification_id, user_id))
    if row is None:  # also covers other people's notifications: their existence is not revealed
        raise ApiError(404, "That notification does not exist.")
    db = get_db()
    with db:
        db.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    return notification_json(one("SELECT * FROM notifications WHERE id = ?", (notification_id,)))


def mark_all_read(user_id: str) -> dict:
    db = get_db()
    with db:
        cur = db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
    return {"updated": cur.rowcount}


def dashboard(user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    week_ahead, week_ago = to_iso(now + timedelta(days=7)), to_iso(now - timedelta(days=7))
    groups = one("SELECT COUNT(*) AS n FROM memberships WHERE user_id = ?", (user_id,))["n"]
    mine = "s.group_id IN (SELECT group_id FROM memberships WHERE user_id = :uid)"
    this_week = one(f"SELECT COUNT(*) AS n FROM study_sessions s WHERE {mine} AND s.starts_at > :now AND s.starts_at < :ahead", {"uid": user_id, "now": now_iso(), "ahead": week_ahead})["n"]
    new_resources = one(
        "SELECT COUNT(*) AS n FROM resources r WHERE r.group_id IN (SELECT group_id FROM memberships WHERE user_id = ?) AND r.uploaded_by != ? AND r.created_at > ?",
        (user_id, user_id, week_ago),
    )["n"]
    sessions = all_rows(f"{SESSION_SQL} WHERE {mine} AND s.starts_at > :now ORDER BY s.starts_at LIMIT 3", {"uid": user_id, "now": now_iso()})
    my_groups = all_rows(GROUP_SQL + " WHERE g.id IN (SELECT group_id FROM memberships WHERE user_id = :uid) ORDER BY g.name LIMIT 3", {"uid": user_id, "now": now_iso()})
    return {
        "counts": {"groups": groups, "sessionsThisWeek": this_week, "newResources": new_resources},
        "upcomingSessions": [session_json(r) for r in sessions],
        "myGroups": [group_json(r) for r in my_groups],
    }
