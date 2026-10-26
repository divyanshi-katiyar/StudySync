"""Resources, discussion posts and comments."""
from flask import request

from ..db import all_rows, get_db, one
from ..errors import ApiError
from ..utils import like_pattern, new_id, now_iso
from ..validation import check, clean_tags, int_arg, max_length, min_length, one_of, required, text, url_rule
from .common import is_staff, membership_of, notify, other_member_ids, require_member, user_name

RESOURCE_TYPES = ("link", "file", "note")
RESOURCE_SQL = "SELECT r.*, u.name AS uploader_name FROM resources r LEFT JOIN users u ON u.id = r.uploaded_by"
TITLE_RULES = [required("a title"), min_length(3, "Title"), max_length(100, "Title")]


# ---------- resources ----------
def _tags_for(ids: list[str]) -> dict:
    tags: dict[str, list] = {i: [] for i in ids}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in all_rows(f"SELECT resource_id, tag FROM resource_tags WHERE resource_id IN ({marks}) ORDER BY tag", ids):
            tags[r["resource_id"]].append(r["tag"])
    return tags


def _resource_json(row, tags, viewer_id, staff) -> dict:
    return {
        "id": row["id"], "groupId": row["group_id"], "uploadedBy": row["uploaded_by"], "uploaderName": row["uploader_name"] or "Former member",
        "title": row["title"], "type": row["type"], "url": row["url"], "body": row["body"], "tags": tags,
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "canDelete": row["uploaded_by"] == viewer_id or staff,
    }


def list_resources(group_id: str, user_id: str):
    staff = is_staff(require_member(group_id, user_id))
    rtype = request.args.get("type", "")
    if rtype and rtype not in RESOURCE_TYPES:
        raise ApiError(422, "Please fix the query parameters.", {"type": "type must be link, file or note."})
    search = text(request.args.get("search", ""))[:100]
    tag = text(request.args.get("tag", "")).lower().lstrip("#")
    limit, page = int_arg("limit", 100, 1, 100), int_arg("page", 1, 1, 10_000)
    where, params = ["r.group_id = :gid"], {"gid": group_id}
    if rtype:
        where.append("r.type = :type")
        params["type"] = rtype
    if tag:
        where.append("EXISTS (SELECT 1 FROM resource_tags t WHERE t.resource_id = r.id AND t.tag = :tag)")
        params["tag"] = tag
    if search:
        where.append("(r.title LIKE :q ESCAPE '\\' OR EXISTS (SELECT 1 FROM resource_tags t WHERE t.resource_id = r.id AND t.tag LIKE :q ESCAPE '\\'))")
        params["q"] = like_pattern(search.lstrip("#"))
    clause = " WHERE " + " AND ".join(where)
    total = one("SELECT COUNT(*) AS n FROM resources r" + clause, params)["n"]
    rows = all_rows(f"{RESOURCE_SQL}{clause} ORDER BY r.created_at DESC LIMIT :limit OFFSET :offset", {**params, "limit": limit, "offset": (page - 1) * limit})
    tags = _tags_for([r["id"] for r in rows])
    return [_resource_json(r, tags[r["id"]], user_id, staff) for r in rows], total


def _resource_rules(rtype, data):
    rules = {"title": TITLE_RULES, "type": [one_of(RESOURCE_TYPES, "Choose a type.")]}
    if rtype == "note":
        rules["body"] = [required("your note"), min_length(10, "Note"), max_length(5000, "Note")]
    else:
        rules["url"] = [required("a link"), url_rule]
    return rules


def add_resource(group_id: str, user_id: str, data: dict) -> dict:
    membership = require_member(group_id, user_id)
    rtype = data.get("type")
    check(_resource_rules(rtype, data), data)
    tags = clean_tags(data.get("tags"))
    rid, db = new_id("r"), get_db()
    with db:
        db.execute(
            "INSERT INTO resources (id, group_id, uploaded_by, title, type, url, body, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (rid, group_id, user_id, text(data["title"]), rtype, "" if rtype == "note" else text(data["url"]), text(data["body"]) if rtype == "note" else "", now_iso()),
        )
        db.executemany("INSERT INTO resource_tags (resource_id, tag) VALUES (?,?)", [(rid, t) for t in tags])
        group = one("SELECT name FROM study_groups WHERE id = ?", (group_id,))
        notify(other_member_ids(group_id, user_id), "resource", f"{user_name(user_id)} shared a new resource in {group['name']}", f"/app/groups/{group_id}?tab=resources")
    return _resource_json(one(RESOURCE_SQL + " WHERE r.id = ?", (rid,)), tags, user_id, is_staff(membership))


def _resource_or_404(resource_id: str):
    row = one(RESOURCE_SQL + " WHERE r.id = ?", (resource_id,))
    if row is None:
        raise ApiError(404, "That resource no longer exists.")
    return row


def _can_change_resource(row, user_id):
    membership = membership_of(row["group_id"], user_id)
    if membership is None:
        raise ApiError(403, "Join this group to see its content.")
    if row["uploaded_by"] != user_id and not is_staff(membership):
        raise ApiError(403, "Only the uploader or a moderator can change this.")
    return membership


def update_resource(resource_id: str, user_id: str, data: dict) -> dict:
    row = _resource_or_404(resource_id)
    membership = _can_change_resource(row, user_id)
    rules = {}
    if "title" in data:
        rules["title"] = TITLE_RULES
    if "url" in data and row["type"] != "note":
        rules["url"] = [required("a link"), url_rule]
    if "body" in data and row["type"] == "note":
        rules["body"] = [required("your note"), min_length(10, "Note"), max_length(5000, "Note")]
    if not rules and "tags" not in data:
        raise ApiError(422, "Please fix the highlighted fields.", {"title": "Send at least one field to update."})
    check(rules, data)
    tags = clean_tags(data["tags"]) if "tags" in data else None
    db = get_db()
    with db:
        for field in rules:
            db.execute(f"UPDATE resources SET {field} = ?, updated_at = ? WHERE id = ?", (text(data[field]), now_iso(), resource_id))
        if tags is not None:
            db.execute("DELETE FROM resource_tags WHERE resource_id = ?", (resource_id,))
            db.executemany("INSERT INTO resource_tags (resource_id, tag) VALUES (?,?)", [(resource_id, t) for t in tags])
            db.execute("UPDATE resources SET updated_at = ? WHERE id = ?", (now_iso(), resource_id))
    fresh = _resource_or_404(resource_id)
    return _resource_json(fresh, _tags_for([resource_id])[resource_id], user_id, is_staff(membership))


def delete_resource(resource_id: str, user_id: str):
    row = _resource_or_404(resource_id)
    _can_change_resource(row, user_id)
    db = get_db()
    with db:
        db.execute("DELETE FROM resources WHERE id = ?", (resource_id,))


# ---------- posts ----------
POST_RULES = {"title": [required("a title"), min_length(5, "Title"), max_length(120, "Title")], "body": [required("some details"), min_length(10, "Details"), max_length(5000, "Details")]}
POST_SQL = (
    "SELECT p.*, u.name AS author_name, (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count "
    "FROM posts p LEFT JOIN users u ON u.id = p.author_id"
)


def _post_json(row, viewer_id, staff) -> dict:
    mine = row["author_id"] == viewer_id
    return {
        "id": row["id"], "groupId": row["group_id"], "authorId": row["author_id"], "authorName": row["author_name"] or "Former member",
        "title": row["title"], "body": row["body"], "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        "commentCount": row["comment_count"], "canEdit": mine, "canDelete": mine or staff,
    }


def list_posts(group_id: str, user_id: str):
    staff = is_staff(require_member(group_id, user_id))
    limit, page = int_arg("limit", 50, 1, 100), int_arg("page", 1, 1, 10_000)
    total = one("SELECT COUNT(*) AS n FROM posts WHERE group_id = ?", (group_id,))["n"]
    rows = all_rows(f"{POST_SQL} WHERE p.group_id = ? ORDER BY p.created_at DESC LIMIT ? OFFSET ?", (group_id, limit, (page - 1) * limit))
    return [_post_json(r, user_id, staff) for r in rows], total


def create_post(group_id: str, user_id: str, data: dict) -> dict:
    membership = require_member(group_id, user_id)
    check(POST_RULES, data)
    pid, db = new_id("p"), get_db()
    with db:
        db.execute("INSERT INTO posts (id, group_id, author_id, title, body, created_at) VALUES (?,?,?,?,?,?)", (pid, group_id, user_id, text(data["title"]), text(data["body"]), now_iso()))
        group = one("SELECT name FROM study_groups WHERE id = ?", (group_id,))
        notify(other_member_ids(group_id, user_id), "post", f"{user_name(user_id)} started a discussion in {group['name']}", f"/app/groups/{group_id}/posts/{pid}")
    return _post_json(one(POST_SQL + " WHERE p.id = ?", (pid,)), user_id, is_staff(membership))


def _post_or_404(post_id: str):
    row = one(POST_SQL + " WHERE p.id = ?", (post_id,))
    if row is None:
        raise ApiError(404, "That post does not exist.")
    return row


def _comment_json(row, viewer_id, staff) -> dict:
    return {
        "id": row["id"], "postId": row["post_id"], "authorId": row["author_id"], "authorName": row["author_name"] or "Former member",
        "body": row["body"], "createdAt": row["created_at"], "canDelete": row["author_id"] == viewer_id or staff,
    }


def get_post(post_id: str, user_id: str) -> dict:
    row = _post_or_404(post_id)
    staff = is_staff(require_member(row["group_id"], user_id))
    group = one("SELECT id, name FROM study_groups WHERE id = ?", (row["group_id"],))
    comments = all_rows("SELECT c.*, u.name AS author_name FROM comments c LEFT JOIN users u ON u.id = c.author_id WHERE c.post_id = ? ORDER BY c.created_at", (post_id,))
    data = _post_json(row, user_id, staff)
    data["group"] = {"id": group["id"], "name": group["name"]}
    data["comments"] = [_comment_json(c, user_id, staff) for c in comments]
    return data


def update_post(post_id: str, user_id: str, data: dict) -> dict:
    row = _post_or_404(post_id)
    staff = is_staff(require_member(row["group_id"], user_id))
    if row["author_id"] != user_id:
        raise ApiError(403, "Only the author can edit this post.")
    fields = {k: v for k, v in data.items() if k in POST_RULES}
    if not fields:
        raise ApiError(422, "Please fix the highlighted fields.", {"title": "Send a title or details to update."})
    check({k: POST_RULES[k] for k in fields}, fields)
    db = get_db()
    with db:
        for field, value in fields.items():
            db.execute(f"UPDATE posts SET {field} = ?, updated_at = ? WHERE id = ?", (text(value), now_iso(), post_id))
    return _post_json(_post_or_404(post_id), user_id, staff)


def delete_post(post_id: str, user_id: str):
    row = _post_or_404(post_id)
    staff = is_staff(require_member(row["group_id"], user_id))
    if row["author_id"] != user_id and not staff:
        raise ApiError(403, "Only the author or a moderator can delete this post.")
    db = get_db()
    with db:
        db.execute("DELETE FROM posts WHERE id = ?", (post_id,))


def add_comment(post_id: str, user_id: str, data: dict) -> dict:
    row = _post_or_404(post_id)
    staff = is_staff(require_member(row["group_id"], user_id))
    check({"body": [required("a comment"), min_length(2, "Comment"), max_length(1000, "Comment")]}, data)
    cid, db = new_id("c"), get_db()
    with db:
        db.execute("INSERT INTO comments (id, post_id, author_id, body, created_at) VALUES (?,?,?,?,?)", (cid, post_id, user_id, text(data["body"]), now_iso()))
        if row["author_id"] and row["author_id"] != user_id:
            group = one("SELECT name FROM study_groups WHERE id = ?", (row["group_id"],))
            notify([row["author_id"]], "reply", f"{user_name(user_id)} replied to your post in {group['name']}", f"/app/groups/{row['group_id']}/posts/{post_id}")
    created = one("SELECT c.*, u.name AS author_name FROM comments c LEFT JOIN users u ON u.id = c.author_id WHERE c.id = ?", (cid,))
    return _comment_json(created, user_id, staff)


def delete_comment(comment_id: str, user_id: str):
    comment = one("SELECT c.*, p.group_id FROM comments c JOIN posts p ON p.id = c.post_id WHERE c.id = ?", (comment_id,))
    if comment is None:
        raise ApiError(404, "That comment does not exist.")
    staff = is_staff(require_member(comment["group_id"], user_id))
    if comment["author_id"] != user_id and not staff:
        raise ApiError(403, "Only the author or a moderator can delete this comment.")
    db = get_db()
    with db:
        db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
