"""GET /api/stream: the live event stream (Server-Sent Events)."""
from flask import Blueprint, Response, current_app, g

from ..errors import ApiError
from ..realtime import event_stream
from ..security import auth_required, uid

bp = Blueprint("stream", __name__, url_prefix="/api")


@bp.get("/stream")
@auth_required
def stream():
    hub = current_app.extensions["hub"]
    sub = hub.subscribe(uid(), current_app.config["SSE_MAX_STREAMS_PER_USER"])
    if sub is None:
        raise ApiError(429, "Too many open live connections for this account. Close another tab and try again.")
    body = event_stream(hub, sub, uid(), g.token_exp, current_app.config["SSE_HEARTBEAT_SECONDS"])
    response = Response(body, mimetype="text/event-stream")
    response.headers["X-Accel-Buffering"] = "no"  # tell nginx-style proxies not to buffer the stream
    return response
