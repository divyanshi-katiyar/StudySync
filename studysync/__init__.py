"""StudySync API application factory."""
import logging
import time
import uuid

from flask import Flask, g, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_config
from .db import close_db, get_db, init_db
from .errors import ApiError, register_error_handlers
from .ratelimit import RateLimiter
from .utils import now_iso, ok

log = logging.getLogger("studysync")
AUTH_ENDPOINTS = {"auth.login", "auth.register", "auth.refresh"}


def create_app(overrides: dict | None = None) -> Flask:
    overrides = overrides or {}
    app = Flask(__name__)
    app.config.update(load_config(overrides.get("ENV")))
    app.config.update(overrides)
    app.json.sort_keys = False
    app.json.ensure_ascii = False
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init_db(app.config["DATABASE"])
    app.extensions["limiter"] = RateLimiter()
    app.teardown_appcontext(close_db)
    register_error_handlers(app)

    from .routes import auth, content, groups, sessions, users

    for module in (auth, users, groups, content, sessions):
        app.register_blueprint(module.bp)

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1")
        return ok({"status": "ok", "time": now_iso()})

    @app.before_request
    def start_request():
        g.started = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id", "")[:64] or uuid.uuid4().hex[:12]
        if not app.config["RATE_LIMIT_ENABLED"] or request.method == "OPTIONS":
            return
        limiter, ip = app.extensions["limiter"], request.remote_addr or "unknown"
        checks = [(f"global:{ip}", app.config["RATE_LIMIT_GLOBAL"])]
        if request.endpoint in AUTH_ENDPOINTS:
            checks.append((f"auth:{ip}", app.config["RATE_LIMIT_AUTH"]))
        if request.endpoint == "groups.join_by_code":
            checks.append((f"code:{ip}", app.config["RATE_LIMIT_JOIN_CODE"]))
        for key, (limit, window) in checks:
            allowed, retry = limiter.hit(key, limit, window)
            if not allowed:
                raise ApiError(429, "Too many requests. Please slow down and try again shortly.", headers={"Retry-After": str(retry)})

    @app.after_request
    def finish_request(response):
        origin = request.headers.get("Origin")
        if origin and origin in app.config["CORS_ORIGINS"]:  # exact-match allow-list, never "*"
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Request-Id, Retry-After"
            response.headers.add("Vary", "Origin")
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                response.headers["Access-Control-Max-Age"] = "600"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        if app.config["COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        if not app.config["TESTING"]:
            log.info("%s %s -> %s in %.1f ms [%s]", request.method, request.path, response.status_code, (time.perf_counter() - g.started) * 1000, g.request_id)
        return response

    return app
