"""Resources, posts and comments."""
from flask import Blueprint, jsonify

from ..security import auth_required, uid
from ..services import content as service
from ..utils import ok
from ..validation import json_body

bp = Blueprint("content", __name__, url_prefix="/api")


def _list_response(items, total):
    response = jsonify({"success": True, "data": items})
    response.headers["X-Total-Count"] = str(total)
    return response


@bp.get("/groups/<group_id>/resources")
@auth_required
def list_resources(group_id):
    return _list_response(*service.list_resources(group_id, uid()))


@bp.post("/groups/<group_id>/resources")
@auth_required
def add_resource(group_id):
    return ok(service.add_resource(group_id, uid(), json_body()), 201)


@bp.patch("/resources/<resource_id>")
@auth_required
def update_resource(resource_id):
    return ok(service.update_resource(resource_id, uid(), json_body()))


@bp.delete("/resources/<resource_id>")
@auth_required
def delete_resource(resource_id):
    service.delete_resource(resource_id, uid())
    return ok({"ok": True})


@bp.get("/groups/<group_id>/posts")
@auth_required
def list_posts(group_id):
    return _list_response(*service.list_posts(group_id, uid()))


@bp.post("/groups/<group_id>/posts")
@auth_required
def create_post(group_id):
    return ok(service.create_post(group_id, uid(), json_body()), 201)


@bp.get("/posts/<post_id>")
@auth_required
def get_post(post_id):
    return ok(service.get_post(post_id, uid()))


@bp.patch("/posts/<post_id>")
@auth_required
def update_post(post_id):
    return ok(service.update_post(post_id, uid(), json_body()))


@bp.delete("/posts/<post_id>")
@auth_required
def delete_post(post_id):
    service.delete_post(post_id, uid())
    return ok({"ok": True})


@bp.post("/posts/<post_id>/comments")
@auth_required
def add_comment(post_id):
    return ok(service.add_comment(post_id, uid(), json_body()), 201)


@bp.delete("/comments/<comment_id>")
@auth_required
def delete_comment(comment_id):
    service.delete_comment(comment_id, uid())
    return ok({"ok": True})
