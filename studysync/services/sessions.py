"""Study sessions and RSVPs."""
from datetime import datetime, timezone

from flask import request

from ..db import all_rows, get_db, one
from ..errors import ApiError
from ..serializers import SESSION_SQL, session_json
from ..utils import new_id, now_iso, parse_iso, to_iso
from ..validation import check, int_arg, max_length, min_length, one_of, required, text, url_rule
from .common import is_staff, notify, other_member_ids, require_member, user_name

TITLE_RULES = [required("a title"), min_length(3, "Title"), max_length(100, "Title")]


def _starts_at_rule(v):
    when = parse_iso(v)
    if when is None:
        return "Pick a date and time."
    return "Pick a time in the future." if when <= datetime.now(timezone.utc) else ""


def _duration_rule(v):
    return "" if isinstance(v, int) and not isinstance(v, bool) and 15 <= v <= 300 else "Enter a length between 15 and 300 minutes."


def _link_rule(v):
    return "" if v in (None, "") or (isinstance(v, str) and not v.strip()) else url_rule(v)


def _normalise(data: dict) -> dict:
    """The form sends the length as a string ('60'); accept whole numbers in either form."""
    data = dict(data)
    value = data.get("durationMin")
    if isinstance(value, str) and value.strip().isdigit():
        data["durationMin"] = int(value.strip())
    return data


def _session(session_id: str, user_id: str):
    row = one(SESSION_SQL + " WHERE s.id = :id", {"id": session_id, "uid": user_id})
    if row is None:
        raise ApiError(404, "That session no longer exists.")
    return row


def list_for_group(group_id: str, user_id: str) -> list:
    require_member(group_id, user_id)
    rows = all_rows(SESSION_SQL + " WHERE s.group_id = :gid ORDER BY s.starts_at", {"gid": group_id, "uid": user_id})
    return [session_json(r) for r in rows]


def upcoming(user_id: str) -> list:
    limit = int_arg("limit", 50, 1, 100)
    rows = all_rows(
        SESSION_SQL + " WHERE s.group_id IN (SELECT group_id FROM memberships WHERE user_id = :uid) AND s.starts_at > :now ORDER BY s.starts_at LIMIT :limit",
        {"uid": user_id, "now": now_iso(), "limit": limit},
    )
    return [session_json(r) for r in rows]


def create_session(group_id: str, user_id: str, data: dict) -> dict:
    membership = require_member(group_id, user_id)
    if not is_staff(membership):
        raise ApiError(403, "Only moderators and the owner can schedule sessions.")
    data = _normalise(data)
    check({"title": TITLE_RULES, "startsAt": [_starts_at_rule], "durationMin": [_duration_rule], "meetingLink": [_link_rule]}, data)
    sid, db = new_id("s"), get_db()
    with db:
        db.execute(
            "INSERT INTO study_sessions (id, group_id, created_by, title, starts_at, duration_min, meeting_link, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (sid, group_id, user_id, text(data["title"]), to_iso(parse_iso(data["startsAt"])), data["durationMin"], text(data.get("meetingLink")), now_iso()),
        )
        db.execute("INSERT INTO session_attendees (session_id, user_id, status) VALUES (?,?,'going')", (sid, user_id))  # the organiser is going
        group = one("SELECT name FROM study_groups WHERE id = ?", (group_id,))
        notify(other_member_ids(group_id, user_id), "session", f"{user_name(user_id)} scheduled a session in {group['name']}: {text(data['title'])}", f"/app/groups/{group_id}?tab=sessions")
    return session_json(_session(sid, user_id))


def update_session(session_id: str, user_id: str, data: dict) -> dict:
    row = _session(session_id, user_id)
    if not is_staff(require_member(row["group_id"], user_id)):
        raise ApiError(403, "Only moderators and the owner can change sessions.")
    data = _normalise(data)
    rules = {k: v for k, v in {"title": TITLE_RULES, "startsAt": [_starts_at_rule], "durationMin": [_duration_rule], "meetingLink": [_link_rule]}.items() if k in data}
    if not rules:
        raise ApiError(422, "Please fix the highlighted fields.", {"title": "Send at least one field to update."})
    check(rules, data)
    columns = {"title": "title", "startsAt": "starts_at", "durationMin": "duration_min", "meetingLink": "meeting_link"}
    db = get_db()
    with db:
        for key in rules:  # column names come from the fixed map above
            value = to_iso(parse_iso(data[key])) if key == "startsAt" else data[key] if key == "durationMin" else text(data[key])
            db.execute(f"UPDATE study_sessions SET {columns[key]} = ?, updated_at = ? WHERE id = ?", (value, now_iso(), session_id))
    return session_json(_session(session_id, user_id))


def delete_session(session_id: str, user_id: str):
    row = _session(session_id, user_id)
    if not is_staff(require_member(row["group_id"], user_id)):
        raise ApiError(403, "Only moderators and the owner can delete sessions.")
    db = get_db()
    with db:
        db.execute("DELETE FROM study_sessions WHERE id = ?", (session_id,))


def set_rsvp(session_id: str, user_id: str, data: dict) -> dict:
    row = _session(session_id, user_id)
    require_member(row["group_id"], user_id)
    check({"status": [one_of(("going", "maybe", "no"), "Choose going, maybe or no.")]}, data)
    db = get_db()
    with db:
        db.execute(
            "INSERT INTO session_attendees (session_id, user_id, status) VALUES (?,?,?) ON CONFLICT(session_id, user_id) DO UPDATE SET status = excluded.status",
            (session_id, user_id, data["status"]),
        )
    return session_json(_session(session_id, user_id))
