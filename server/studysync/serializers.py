"""Turn database rows into the JSON shapes the React front end already consumes (camelCase)."""
from .subjects import subject_color


def public_user(row) -> dict:
    return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"], "avatarUrl": row["avatar_url"], "createdAt": row["created_at"]}


GROUP_SQL = """
SELECT g.*, u.name AS owner_name,
  (SELECT COUNT(*) FROM memberships m WHERE m.group_id = g.id) AS member_count,
  (SELECT m.role FROM memberships m WHERE m.group_id = g.id AND m.user_id = :uid) AS my_role,
  (SELECT s.id FROM study_sessions s WHERE s.group_id = g.id AND s.starts_at > :now ORDER BY s.starts_at LIMIT 1) AS next_id,
  (SELECT s.title FROM study_sessions s WHERE s.group_id = g.id AND s.starts_at > :now ORDER BY s.starts_at LIMIT 1) AS next_title,
  (SELECT s.starts_at FROM study_sessions s WHERE s.group_id = g.id AND s.starts_at > :now ORDER BY s.starts_at LIMIT 1) AS next_starts
FROM study_groups g LEFT JOIN users u ON u.id = g.owner_id
"""


def group_json(row) -> dict:
    member = row["my_role"] is not None
    data = {
        "id": row["id"], "name": row["name"], "description": row["description"], "subject": row["subject"],
        "color": subject_color(row["subject"]), "visibility": row["visibility"],
        "ownerId": row["owner_id"], "ownerName": row["owner_name"] or "Former member",
        "createdAt": row["created_at"], "memberCount": row["member_count"],
        "isMember": member, "myRole": row["my_role"],
        "nextSession": {"id": row["next_id"], "title": row["next_title"], "startsAt": row["next_starts"]} if row["next_id"] else None,
    }
    if member:  # the invite code is only ever shown to members
        data["inviteCode"] = row["invite_code"]
    return data


SESSION_SQL = """
SELECT s.*, g.name AS group_name, g.subject AS group_subject, u.name AS created_by_name,
  (SELECT COUNT(*) FROM session_attendees a WHERE a.session_id = s.id AND a.status = 'going') AS going_count,
  (SELECT COUNT(*) FROM session_attendees a WHERE a.session_id = s.id AND a.status = 'maybe') AS maybe_count,
  (SELECT a.status FROM session_attendees a WHERE a.session_id = s.id AND a.user_id = :uid) AS my_rsvp
FROM study_sessions s JOIN study_groups g ON g.id = s.group_id LEFT JOIN users u ON u.id = s.created_by
"""


def session_json(row) -> dict:
    return {
        "id": row["id"], "groupId": row["group_id"], "createdBy": row["created_by"], "createdByName": row["created_by_name"] or "Former member",
        "title": row["title"], "startsAt": row["starts_at"], "durationMin": row["duration_min"], "meetingLink": row["meeting_link"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        "groupName": row["group_name"], "groupColor": subject_color(row["group_subject"]),
        "goingCount": row["going_count"], "maybeCount": row["maybe_count"], "myRsvp": row["my_rsvp"],
    }


def notification_json(row) -> dict:
    return {"id": row["id"], "userId": row["user_id"], "type": row["type"], "message": row["message"], "link": row["link"], "isRead": bool(row["is_read"]), "createdAt": row["created_at"]}
