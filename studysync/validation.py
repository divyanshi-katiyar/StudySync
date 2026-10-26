"""Input validation. Rules mirror the front end's src/utils/validation.js so both sides give the same messages.

Each rule returns an error message or '' (valid). `check()` raises one 422 listing every invalid field.
"""
import re
from urllib.parse import urlparse

from flask import request

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
TAG_RE = re.compile(r"[^a-z0-9_-]")


def text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def required(label):
    return lambda v: "" if text(v) else f"Enter {label}."


def min_length(n, label):
    return lambda v: "" if len(text(v)) >= n else f"{label} needs at least {n} characters."


def max_length(n, label):
    return lambda v: "" if len(text(v)) <= n else f"{label} can have at most {n} characters."


def email_rule(v):
    value = text(v)
    return "" if EMAIL_RE.match(value) and len(value) <= 254 else "Enter a valid email address, like you@college.edu."


def password_rule(v):
    ok = isinstance(v, str) and PASSWORD_RE.match(v) and len(v) <= 128
    return "" if ok else "Use 8 to 128 characters with a letter and a number."


def url_rule(v):
    value = text(v)
    if len(value) > 2048:
        return "That link is too long."
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "Enter a full link that starts with http:// or https://."
    return ""


def one_of(options, message):
    return lambda v: "" if isinstance(v, str) and v in options else message


def validate(rules: dict, values: dict) -> dict:
    errors = {}
    for field, field_rules in rules.items():
        for rule in field_rules:
            message = rule(values.get(field))
            if message:
                errors[field] = message
                break
    return errors


def check(rules: dict, values: dict):
    errors = validate(rules, values)
    if errors:
        raise ApiError(422, "Please fix the highlighted fields.", errors)


def json_body() -> dict:
    if not request.is_json:
        raise ApiError(415, "Send the request body as JSON (Content-Type: application/json).")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "The request body must be a JSON object.")
    return data


def int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(422, "Please fix the query parameters.", {name: f"{name} must be a whole number."})
    return max(minimum, min(maximum, value))


def clean_tags(value) -> list[str]:
    """Lower-case, strip '#', replace spaces with '-', drop invalid characters, de-duplicate, keep at most 6."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ApiError(422, "Please fix the highlighted fields.", {"tags": "Tags must be a list."})
    tags = []
    for item in value:
        if not isinstance(item, str):
            raise ApiError(422, "Please fix the highlighted fields.", {"tags": "Each tag must be text."})
        tag = TAG_RE.sub("", item.strip().lower().lstrip("#").replace(" ", "-"))[:30]
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:6]
