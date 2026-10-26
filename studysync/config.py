"""Environment-based configuration. Every value can be overridden with an environment variable."""
import os

DEV_SECRET = "dev-only-secret-change-me"


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def load_config(env_name: str | None = None) -> dict:
    env = (env_name or os.environ.get("STUDYSYNC_ENV", "development")).lower()
    cfg = {
        "ENV": env,
        "SECRET_KEY": os.environ.get("STUDYSYNC_SECRET_KEY", DEV_SECRET),
        "DATABASE": os.environ.get("STUDYSYNC_DATABASE", "studysync.db"),
        "CORS_ORIGINS": [o.strip() for o in os.environ.get("STUDYSYNC_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
        "COOKIE_SECURE": _bool("STUDYSYNC_COOKIE_SECURE", env == "production"),
        "COOKIE_SAMESITE": os.environ.get("STUDYSYNC_COOKIE_SAMESITE", "Lax"),
        "TRUST_PROXY": _bool("STUDYSYNC_TRUST_PROXY", False),
        "ACCESS_TOKEN_MINUTES": 15,
        "REFRESH_TOKEN_DAYS": 7,
        "PASSWORD_HASH_METHOD": "scrypt",
        "MAX_CONTENT_LENGTH": 1_000_000,  # 1 MB request bodies
        # Rate limits: (max requests, window in seconds)
        "RATE_LIMIT_ENABLED": True,
        "RATE_LIMIT_GLOBAL": (300, 60),
        "RATE_LIMIT_AUTH": (10, 60),
        "RATE_LIMIT_LOGIN_FAILURES": (5, 900),
        "RATE_LIMIT_JOIN_CODE": (10, 60),
        "TESTING": False,
    }
    if env == "testing":
        cfg.update(TESTING=True, PASSWORD_HASH_METHOD="pbkdf2:sha256:1000", SECRET_KEY="test-secret-key-for-unit-tests-0123456789", RATE_LIMIT_ENABLED=False)
    if env == "production" and cfg["SECRET_KEY"] == DEV_SECRET:
        raise RuntimeError("STUDYSYNC_SECRET_KEY must be set to a long random value in production.")
    return cfg
