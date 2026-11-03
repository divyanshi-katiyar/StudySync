"""/api/auth/*: register, login, refresh, logout."""
from flask import Blueprint, current_app, jsonify, request

from ..errors import ApiError, error_response
from ..security import (REFRESH_COOKIE, auth_required, clear_refresh_cookie, create_access_token, enforce_trusted_origin,
                        issue_refresh_token, revoke_refresh_token, rotate_refresh_token, set_refresh_cookie, uid)
from ..serializers import public_user
from ..services import auth as service
from ..db import one
from ..utils import ok
from ..validation import json_body, text

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _session_response(user, status=200):
    token, expires_in = create_access_token(user["id"])
    response = jsonify({"success": True, "data": {"user": public_user(user), "accessToken": token, "expiresIn": expires_in}})
    response.status_code = status
    set_refresh_cookie(response, issue_refresh_token(user["id"]))
    return response


@bp.post("/register")
def register():
    return _session_response(service.register(json_body()), 201)


@bp.post("/login")
def login():
    data = json_body()
    limiter, (limit, window) = current_app.extensions["limiter"], current_app.config["RATE_LIMIT_LOGIN_FAILURES"]
    key = f"login-fail:{request.remote_addr}:{text(data.get('email')).lower()}"
    if current_app.config["RATE_LIMIT_ENABLED"]:
        blocked, retry = limiter.blocked(key, limit, window)
        if blocked:
            raise ApiError(429, "Too many failed attempts. Try again later.", headers={"Retry-After": str(retry)})
    try:
        user = service.authenticate(data)
    except ApiError as err:
        if err.status == 401:
            limiter.record(key)
        raise
    limiter.clear(key)
    return _session_response(user)


@bp.post("/refresh")
def refresh():
    enforce_trusted_origin()
    try:
        user_id, new_token = rotate_refresh_token(request.cookies.get(REFRESH_COOKIE))
    except ApiError as err:
        response = error_response(err.status, err.message)
        clear_refresh_cookie(response)
        return response
    user = one("SELECT * FROM users WHERE id = ?", (user_id,))
    token, expires_in = create_access_token(user_id)
    response = jsonify({"success": True, "data": {"user": public_user(user), "accessToken": token, "expiresIn": expires_in}})
    set_refresh_cookie(response, new_token)
    return response


@bp.post("/logout")
def logout():
    # Public on purpose: a user whose access token has expired must still be able to end the session.
    enforce_trusted_origin()
    revoke_refresh_token(request.cookies.get(REFRESH_COOKIE))
    response = jsonify({"success": True, "data": {"ok": True}})
    clear_refresh_cookie(response)
    return response
