import secrets
import sqlite3

from flask import request

from ..db import all_rows, get_db, one
from ..errors import ApiError
from ..serializers import GROUP_SQL, group_json
from ..subjects import SUBJECTS
from ..utils import like_pattern, new_id, now_iso
from ..validation import check, int_arg, max_length, min_length, one_of, required, text
from .common import group_row_or_404, membership_of, notify, other_member_ids, require_member, user_name

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I so codes are easy to read aloud
GROUP_RULES = {
    "name": [required("a group name"), min_length(3, "Group name"), max_length(60, "Group name")],
    "description": [required("a short description"), min_length(10, "Description"), max_length(300, "Description")],
    "subject": [one_of(SUBJECTS, "Choose a subject.")],
    "visibility": [one_of(("public", "private"), "Choose who can find this group.")],
}


def _group(group_id: str, user_id: str):
    row = one(GROUP_SQL + " WHERE g.id = :id", {"id": group_id, "uid": user_id, "now": now_iso()})
    if row is None:
        raise ApiError(404, "That group does not exist.")
    return row


def get_group(group_id: str, user_id: str) -> dict:
    row = _group(group_id, user_id)
    if row["visibility"] == "private" and row["my_role"] is None:
        raise ApiError(403, "This group is private. Ask the owner for an invite code.")
    return group_json(row)


def discover(user_id: str) -> dict:
    search = text(request.args.get("search", ""))[:100]
    subject = text(request.args.get("subject", ""))
    sort = request.args.get("sort", "popular")
    if sort not in ("popular", "newest"):
        raise ApiError(422, "Please fix the query parameters.", {"sort": "sort must be popular or newest."})
    limit = int_arg("limit", 6, 1, 50)
    page = int_arg("page", 1, 1, 10_000)
    where, params = ["g.visibility = 'public'"], {"uid": user_id, "now": now_iso()}
    if subject:
        where.append("g.subject = :subject")
        params["subject"] = subject
    if search:
        where.append("(g.name LIKE :q ESCAPE '\\' OR g.subject LIKE :q ESCAPE '\\' OR g.description LIKE :q ESCAPE '\\')")
        params["q"] = like_pattern(search)
    clause = " WHERE " + " AND ".join(where)
    total = one("SELECT COUNT(*) AS n FROM study_groups g" + clause, params)["n"]
    pages = max(1, -(-total // limit))
    page = min(page, pages)
    order = "member_count DESC, g.name" if sort == "popular" else "g.created_at DESC"
    rows = all_rows(f"{GROUP_SQL}{clause} ORDER BY {order} LIMIT :limit OFFSET :offset", {**params, "limit": limit, "offset": (page - 1) * limit})
    return {"items": [group_json(r) for r in rows], "total": total, "page": page, "pages": pages}


def my_groups(user_id: str) -> list:
    rows = all_rows(GROUP_SQL + " WHERE g.id IN (SELECT group_id FROM memberships WHERE user_id = :uid) ORDER BY g.name", {"uid": user_id, "now": now_iso()})
    return [group_json(r) for r in rows]


def _new_invite_code(subject: str) -> str:
    prefix = "".join(c for c in subject.upper() if c.isalpha())[:3] or "GRP"
    return f"{prefix}-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def create_group(user_id: str, data: dict) -> dict:
    check(GROUP_RULES, data)
    db = get_db()
    group_id = new_id("g")
    for _ in range(10):
        try:
            with db:
                db.execute(
                    "INSERT INTO study_groups (id, name, description, subject, visibility, invite_code, owner_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (group_id, text(data["name"]), text(data["description"]), data["subject"], data["visibility"], _new_invite_code(data["subject"]), user_id, now_iso()),
                )
                db.execute("INSERT INTO memberships (id, group_id, user_id, role, joined_at) VALUES (?,?,?,?,?)", (new_id("m"), group_id, user_id, "owner", now_iso()))
            return group_json(_group(group_id, user_id))
        except sqlite3.IntegrityError:
            continue  # invite-code collision (astronomically rare): try another code
    raise ApiError(500, "Could not create the group. Please try again.")


def update_group(group_id: str, user_id: str, data: dict) -> dict:
    membership = require_member(group_id, user_id)
    if membership["role"] != "owner":
        raise ApiError(403, "Only the owner can edit this group.")
    fields = {k: v for k, v in data.items() if k in GROUP_RULES}
    if not fields:
        raise ApiError(422, "Please fix the highlighted fields.", {"name": "Send at least one field to update."})
    check({k: GROUP_RULES[k] for k in fields}, fields)
    columns = {"name": "name", "description": "description", "subject": "subject", "visibility": "visibility"}
    db = get_db()
    with db:
        for key, value in fields.items():  # column names come from the fixed map above, never from the request
            db.execute(f"UPDATE study_groups SET {columns[key]} = ? WHERE id = ?", (text(value), group_id))
    return group_json(_group(group_id, user_id))


def delete_group(group_id: str, user_id: str):
    membership = require_member(group_id, user_id)
    if membership["role"] != "owner":
        raise ApiError(403, "Only the owner can delete a group.")
    db = get_db()
    with db:  # memberships, resources, posts, comments and sessions go with it (ON DELETE CASCADE)
        db.execute("DELETE FROM study_groups WHERE id = ?", (group_id,))


def _add_member(group, user_id: str):
    db = get_db()
    with db:
        db.execute("INSERT INTO memberships (id, group_id, user_id, role, joined_at) VALUES (?,?,?,?,?)", (new_id("m"), group["id"], user_id, "member", now_iso()))
        notify(other_member_ids(group["id"], user_id), "member", f"{user_name(user_id)} joined {group['name']}", f"/app/groups/{group['id']}?tab=members")


def join_group(group_id: str, user_id: str) -> dict:
    group = group_row_or_404(group_id)
    if group["visibility"] == "private":
        raise ApiError(403, "This group is private. Ask the owner for an invite code.")
    if membership_of(group_id, user_id):
        raise ApiError(409, "You are already in this group.")
    _add_member(group, user_id)
    return group_json(_group(group_id, user_id))


def join_by_code(user_id: str, data: dict) -> dict:
    code = text(data.get("code")).upper() if isinstance(data.get("code"), str) else ""
    if not code:
        raise ApiError(422, "Enter an invite code.", {"code": "Enter an invite code."})
    group = one("SELECT * FROM study_groups WHERE invite_code = ?", (code,))
    if group is None:
        raise ApiError(404, "No group matches that invite code.", {"code": "No group matches that code. Check it and try again."})
    if membership_of(group["id"], user_id):
        raise ApiError(409, "You are already in this group.", {"code": "You are already in this group."})
    _add_member(group, user_id)
    return group_json(_group(group["id"], user_id))


def leave_group(group_id: str, user_id: str):
    membership = require_member(group_id, user_id)
    if membership["role"] == "owner":
        raise ApiError(409, "Owners cannot leave their own group. Transfer ownership or delete the group.")
    db = get_db()
    with db:
        db.execute("DELETE FROM memberships WHERE id = ?", (membership["id"],))


def list_members(group_id: str, user_id: str) -> list:
    require_member(group_id, user_id)
    rows = all_rows(
        "SELECT m.user_id, m.role, m.joined_at, u.name FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.group_id = ? "
        "ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'moderator' THEN 1 ELSE 2 END, u.name",
        (group_id,),
    )
    return [{"userId": r["user_id"], "name": r["name"], "role": r["role"], "joinedAt": r["joined_at"]} for r in rows]


def set_member_role(group_id: str, user_id: str, target_id: str, data: dict):
    mine = require_member(group_id, user_id)
    if mine["role"] != "owner":
        raise ApiError(403, "Only the owner can change roles.")
    target = membership_of(group_id, target_id)
    if target is None or target["role"] == "owner":
        raise ApiError(404, "That member cannot be changed.")
    check({"role": [one_of(("moderator", "member"), "Choose moderator or member.")]}, data)
    db = get_db()
    with db:
        db.execute("UPDATE memberships SET role = ? WHERE id = ?", (data["role"], target["id"]))
    return {"userId": target_id, "role": data["role"]}


def remove_member(group_id: str, user_id: str, target_id: str):
    mine = require_member(group_id, user_id)
    target = membership_of(group_id, target_id)
    if target is None or target["role"] == "owner":
        raise ApiError(404, "That member cannot be removed.")
    allowed = mine["role"] == "owner" or (mine["role"] == "moderator" and target["role"] == "member")
    if not allowed:
        raise ApiError(403, "You do not have permission to remove this member.")
    db = get_db()
    with db:
        db.execute("DELETE FROM memberships WHERE id = ?", (target["id"],))


def transfer_ownership(group_id: str, user_id: str, data: dict) -> dict:
    mine = require_member(group_id, user_id)
    if mine["role"] != "owner":
        raise ApiError(403, "Only the owner can transfer ownership.")
    target_id = data.get("userId")
    target = membership_of(group_id, target_id) if isinstance(target_id, str) else None
    if target is None or target["user_id"] == user_id:
        raise ApiError(422, "Please fix the highlighted fields.", {"userId": "Choose another member of this group."})
    db = get_db()
    with db:  # demote first: the database allows only one owner per group
        db.execute("UPDATE memberships SET role = 'moderator' WHERE id = ?", (mine["id"],))
        db.execute("UPDATE memberships SET role = 'owner' WHERE id = ?", (target["id"],))
        db.execute("UPDATE study_groups SET owner_id = ? WHERE id = ?", (target_id, group_id))
    return group_json(_group(group_id, user_id))
