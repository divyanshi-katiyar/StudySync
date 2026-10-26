"""Passwords, JWT access tokens, rotating refresh tokens and the auth_required decorator."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, one
from .errors import ApiError
from .utils import new_id, now_iso, parse_iso, to_iso

REFRESH_COOKIE = "studysync_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
REUSE_GRACE_SECONDS = 10  # a just-rotated token used again within this window is a benign race, not theft


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return generate_password_hash(password, method=current_app.config["PASSWORD_HASH_METHOD"])


def verify_password(stored_hash: str, password: str) -> bool:
    return check_password_hash(stored_hash, password)


def burn_password_check(password: str):
    """Spend the same time as a real check when the email is unknown, so response time does not reveal accounts."""
    cache = current_app.extensions.setdefault("dummy_hash", {})
    if "h" not in cache:
        cache["h"] = hash_password(secrets.token_urlsafe(8))
    verify_password(cache["h"], password)


# ---------- access tokens (JWT, HS256, 15 minutes) ----------
def create_access_token(user_id: str):
    minutes = current_app.config["ACCESS_TOKEN_MINUTES"]
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "typ": "access", "jti": secrets.token_hex(8), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256"), minutes * 60


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],  # explicit allow-list: "alg: none" and other algorithms are rejected
            options={"require": ["exp", "iat", "sub"]},
            leeway=5,
        )
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "Your session has expired. Please sign in again.", headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})
    except jwt.InvalidTokenError:
        raise ApiError(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    if payload.get("typ") != "access":
        raise ApiError(401, "Sign in to continue.")
    return payload


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise ApiError(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
        payload = decode_access_token(token.strip())
        user = one("SELECT * FROM users WHERE id = ?", (payload["sub"],))
        if user is None:
            raise ApiError(401, "Sign in to continue.")
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def uid() -> str:
    return g.user["id"]


# ---------- refresh tokens (random, stored hashed, rotated on every use) ----------
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(user_id: str, family_id: str | None = None) -> str:
    raw = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(days=current_app.config["REFRESH_TOKEN_DAYS"])
    db = get_db()
    with db:
        db.execute(
            "INSERT INTO refresh_tokens (id, user_id, family_id, token_hash, expires_at, created_at) VALUES (?,?,?,?,?,?)",
            (new_id("rt"), user_id, family_id or new_id("fam"), _hash(raw), to_iso(expires), now_iso()),
        )
    return raw


def rotate_refresh_token(raw: str | None):
    """Validate a refresh token, revoke it and issue its successor. Returns (user_id, new_raw_token)."""
    expired = ApiError(401, "Your session has expired. Please sign in again.")
    if not raw:
        raise expired
    db = get_db()
    row = one("SELECT * FROM refresh_tokens WHERE token_hash = ?", (_hash(raw),))
    if row is None:
        raise expired
    now = datetime.now(timezone.utc)
    if row["revoked_at"] is not None:
        revoked_at = parse_iso(row["revoked_at"])
        if revoked_at and (now - revoked_at).total_seconds() > REUSE_GRACE_SECONDS:
            # An old token came back: assume it was stolen and end every session in this family.
            with db:
                db.execute("UPDATE refresh_tokens SET revoked_at = ? WHERE family_id = ? AND revoked_at IS NULL", (now_iso(), row["family_id"]))
        raise expired
    if parse_iso(row["expires_at"]) <= now:
        raise expired
    with db:
        db.execute("UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?", (now_iso(), row["id"]))
    return row["user_id"], issue_refresh_token(row["user_id"], row["family_id"])


def revoke_refresh_token(raw: str | None):
    if raw:
        db = get_db()
        with db:
            db.execute("UPDATE refresh_tokens SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL", (now_iso(), _hash(raw)))


def revoke_all_refresh_tokens(user_id: str):
    db = get_db()
    with db:
        db.execute("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now_iso(), user_id))


def set_refresh_cookie(response, raw: str):
    response.set_cookie(
        REFRESH_COOKIE, raw,
        max_age=current_app.config["REFRESH_TOKEN_DAYS"] * 86400,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite=current_app.config["COOKIE_SAMESITE"],
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response):
    response.set_cookie(
        REFRESH_COOKIE, "", max_age=0, expires=0, httponly=True,
        secure=current_app.config["COOKIE_SECURE"], samesite=current_app.config["COOKIE_SAMESITE"], path=REFRESH_COOKIE_PATH,
    )


def enforce_trusted_origin():
    """Cookie-authenticated endpoints refuse browser requests that come from an origin we do not know (CSRF defence)."""
    origin = request.headers.get("Origin")
    if origin and origin not in current_app.config["CORS_ORIGINS"]:
        raise ApiError(403, "This request came from an origin that is not allowed.")
