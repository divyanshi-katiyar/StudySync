"""/api/groups/*: discovery, groups, membership and roles."""
from flask import Blueprint

from ..security import auth_required, uid
from ..services import groups as service
from ..utils import ok
from ..validation import json_body

bp = Blueprint("groups", __name__, url_prefix="/api/groups")


@bp.get("")
@auth_required
def discover():
    return ok(service.discover(uid()))


@bp.post("")
@auth_required
def create():
    return ok(service.create_group(uid(), json_body()), 201)


@bp.get("/mine")
@auth_required
def mine():
    return ok(service.my_groups(uid()))


@bp.post("/join-by-code")
@auth_required
def join_by_code():
    return ok(service.join_by_code(uid(), json_body()))


@bp.get("/<group_id>")
@auth_required
def detail(group_id):
    return ok(service.get_group(group_id, uid()))


@bp.patch("/<group_id>")
@auth_required
def update(group_id):
    return ok(service.update_group(group_id, uid(), json_body()))


@bp.delete("/<group_id>")
@auth_required
def delete(group_id):
    service.delete_group(group_id, uid())
    return ok({"ok": True})


@bp.post("/<group_id>/join")
@auth_required
def join(group_id):
    return ok(service.join_group(group_id, uid()))


@bp.delete("/<group_id>/leave")
@auth_required
def leave(group_id):
    service.leave_group(group_id, uid())
    return ok({"ok": True})


@bp.post("/<group_id>/transfer-ownership")
@auth_required
def transfer(group_id):
    return ok(service.transfer_ownership(group_id, uid(), json_body()))


@bp.get("/<group_id>/members")
@auth_required
def members(group_id):
    return ok(service.list_members(group_id, uid()))


@bp.patch("/<group_id>/members/<target_id>")
@auth_required
def set_role(group_id, target_id):
    return ok(service.set_member_role(group_id, uid(), target_id, json_body()))


@bp.delete("/<group_id>/members/<target_id>")
@auth_required
def remove_member(group_id, target_id):
    service.remove_member(group_id, uid(), target_id)
    return ok({"ok": True})
