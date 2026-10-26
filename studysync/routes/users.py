"""/api/users/me, change password and dashboard."""
from flask import Blueprint, g

from ..security import auth_required, uid
from ..serializers import public_user
from ..services import auth as auth_service
from ..services import notifications as dashboard_service
from ..db import one
from ..utils import ok
from ..validation import json_body

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("/me")
@auth_required
def me():
    return ok(public_user(g.user))


@bp.patch("/me")
@auth_required
def update_me():
    return ok(public_user(auth_service.update_profile(uid(), json_body())))


@bp.post("/me/password")
@auth_required
def change_password():
    auth_service.change_password(g.user, json_body())
    return ok({"ok": True})


@bp.get("/me/dashboard")
@auth_required
def dashboard():
    return ok(dashboard_service.dashboard(uid()))
