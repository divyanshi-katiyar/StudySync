"""Study sessions, RSVPs and notifications."""
from flask import Blueprint

from ..security import auth_required, uid
from ..services import notifications as notes
from ..services import sessions as service
from ..utils import ok
from ..validation import json_body

bp = Blueprint("sessions", __name__, url_prefix="/api")


@bp.get("/groups/<group_id>/sessions")
@auth_required
def list_group_sessions(group_id):
    return ok(service.list_for_group(group_id, uid()))


@bp.post("/groups/<group_id>/sessions")
@auth_required
def create_session(group_id):
    return ok(service.create_session(group_id, uid(), json_body()), 201)


@bp.get("/sessions")
@auth_required
def upcoming():
    return ok(service.upcoming(uid()))


@bp.patch("/sessions/<session_id>")
@auth_required
def update_session(session_id):
    return ok(service.update_session(session_id, uid(), json_body()))


@bp.delete("/sessions/<session_id>")
@auth_required
def delete_session(session_id):
    service.delete_session(session_id, uid())
    return ok({"ok": True})


@bp.put("/sessions/<session_id>/rsvp")
@auth_required
def rsvp(session_id):
    return ok(service.set_rsvp(session_id, uid(), json_body()))


@bp.get("/notifications")
@auth_required
def list_notifications():
    return ok(notes.list_notifications(uid()))


@bp.patch("/notifications/read-all")
@auth_required
def read_all():
    return ok(notes.mark_all_read(uid()))


@bp.patch("/notifications/<notification_id>/read")
@auth_required
def read_one(notification_id):
    return ok(notes.mark_read(notification_id, uid()))
