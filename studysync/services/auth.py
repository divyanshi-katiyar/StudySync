import sqlite3

from ..db import get_db, one
from ..errors import ApiError
from ..security import burn_password_check, hash_password, revoke_all_refresh_tokens, verify_password
from ..utils import new_id, now_iso
from ..validation import check, email_rule, max_length, min_length, password_rule, required, text, url_rule

NAME_RULES = [required("your name"), min_length(2, "Name"), max_length(60, "Name")]


def register(data: dict):
    check({"name": NAME_RULES, "email": [required("your email"), email_rule], "password": [required("a password"), password_rule]}, data)
    email = text(data["email"]).lower()
    if one("SELECT 1 FROM users WHERE email = ?", (email,)):
        raise ApiError(409, "That email is already registered.", {"email": "An account with this email already exists. Try logging in instead."})
    user_id = new_id("u")
    db = get_db()
    try:
        with db:
            db.execute(
                "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?,?,?,?,?)",
                (user_id, text(data["name"]), email, hash_password(data["password"]), now_iso()),
            )
    except sqlite3.IntegrityError:  # two simultaneous sign-ups with the same email
        raise ApiError(409, "That email is already registered.", {"email": "An account with this email already exists. Try logging in instead."})
    return one("SELECT * FROM users WHERE id = ?", (user_id,))


def authenticate(data: dict):
    """Returns the user row, or raises a generic 401 that never says which half was wrong."""
    check({"email": [required("your email"), email_rule], "password": [required("your password")]}, data)
    user = one("SELECT * FROM users WHERE email = ?", (text(data["email"]).lower(),))
    password = data["password"] if isinstance(data["password"], str) else ""
    if user is None:
        burn_password_check(password)
        raise ApiError(401, "The email or password is incorrect.")
    if not verify_password(user["password_hash"], password):
        raise ApiError(401, "The email or password is incorrect.")
    return user


def update_profile(user_id: str, data: dict):
    rules = {}
    if "name" in data:
        rules["name"] = NAME_RULES
    if "avatarUrl" in data:
        rules["avatarUrl"] = [lambda v: "" if v == "" else url_rule(v)]
    if not rules:
        raise ApiError(422, "Please fix the highlighted fields.", {"name": "Send a name or an avatar link to update."})
    check(rules, data)
    db = get_db()
    with db:
        if "name" in data:
            db.execute("UPDATE users SET name = ? WHERE id = ?", (text(data["name"]), user_id))
        if "avatarUrl" in data:
            db.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (text(data["avatarUrl"]), user_id))
    return one("SELECT * FROM users WHERE id = ?", (user_id,))


def change_password(user_row, data: dict):
    check({"currentPassword": [required("your current password")], "newPassword": [required("a new password"), password_rule]}, data)
    current = data["currentPassword"] if isinstance(data["currentPassword"], str) else ""
    if not verify_password(user_row["password_hash"], current):
        raise ApiError(422, "Please fix the highlighted fields.", {"currentPassword": "Your current password is not correct."})
    db = get_db()
    with db:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(data["newPassword"]), user_row["id"]))
    revoke_all_refresh_tokens(user_row["id"])  # other devices must sign in again
