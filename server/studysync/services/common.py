"""Shared lookups and permission checks used by every service."""
from ..db import all_rows, get_db, one
from ..errors import ApiError
from ..realtime import queue_event
from ..utils import new_id, now_iso

STAFF_ROLES = ("owner", "moderator")


def group_row_or_404(group_id: str):
    row = one("SELECT * FROM study_groups WHERE id = ?", (group_id,))
    if row is None:
        raise ApiError(404, "That group does not exist.")
    return row


def membership_of(group_id: str, user_id: str):
    return one("SELECT * FROM memberships WHERE group_id = ? AND user_id = ?", (group_id, user_id))


def require_member(group_id: str, user_id: str):
    """404 when the group is missing, 403 when the caller is not in it. Returns the membership row."""
    group_row_or_404(group_id)
    membership = membership_of(group_id, user_id)
    if membership is None:
        raise ApiError(403, "Join this group to see its content.")
    return membership


def is_staff(membership) -> bool:
    return membership is not None and membership["role"] in STAFF_ROLES


def user_name(user_id: str) -> str:
    row = one("SELECT name FROM users WHERE id = ?", (user_id,))
    return row["name"] if row else "Former member"


def other_member_ids(group_id: str, exclude_user_id: str) -> list[str]:
    return [r["user_id"] for r in all_rows("SELECT user_id FROM memberships WHERE group_id = ? AND user_id != ?", (group_id, exclude_user_id))]


def notify(user_ids, type_: str, message: str, link: str):
    """Notification fan-out: one stored row per recipient so read state is tracked individually, plus a live event for each.
    Runs inside the caller's transaction; the live events are sent after the request succeeds."""
    user_ids, created = list(user_ids), now_iso()
    rows = [(new_id("n"), uid, type_, message, link, created) for uid in user_ids]
    if rows:
        get_db().executemany("INSERT INTO notifications (id, user_id, type, message, link, created_at) VALUES (?,?,?,?,?,?)", rows)
        for nid, uid, _t, _m, _l, _c in rows:
            queue_event([uid], "notification", {"id": nid, "userId": uid, "type": type_, "message": message, "link": link, "isRead": False, "createdAt": created})


def announce(group_id: str, kind: str, exclude_user_id: str | None = None, extra_recipients=(), **extra):
    """Tell the group's members (except the person who acted) that something in the group changed so open pages can refresh."""
    ids = [r["user_id"] for r in all_rows("SELECT user_id FROM memberships WHERE group_id = ?", (group_id,))]
    ids = [i for i in [*ids, *extra_recipients] if i != exclude_user_id]
    queue_event(ids, "group.updated", {"groupId": group_id, "kind": kind, **extra})
