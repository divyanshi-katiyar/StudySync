"""Generate docs/API.md and docs/openapi.yaml from docs/spec.py, with real example responses captured from the running app.

    python scripts/gen_docs.py
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs"))

import yaml  # noqa: E402

import spec  # noqa: E402
from studysync import create_app  # noqa: E402
from studysync.seed import seed_database  # noqa: E402


def capture_examples():
    """Call the real API against seeded demo data and keep (request, status, response) for the main endpoints."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "docs.db")
    seed_database(path)
    app = create_app({"ENV": "testing", "DATABASE": path})
    c = app.test_client()
    out = {}

    def call(key, method, url, body=None, headers=None, keep=None):
        res = getattr(c, method)(url, json=body, headers=headers or {})
        data = res.get_json()
        if keep and isinstance(data.get("data"), list):
            data = {**data, "data": data["data"][:keep]}
        out[key] = (body, res.status_code, data)
        return res.get_json()

    call("POST /api/auth/register", "post", "/api/auth/register", {"name": "Riya Sen", "email": "riya@example.com", "password": "Password123"})
    login = call("POST /api/auth/login", "post", "/api/auth/login", {"email": "demo@studysync.app", "password": "Password123"})
    h = {"Authorization": "Bearer " + login["data"]["accessToken"]}
    call("POST /api/auth/login (wrong)", "post", "/api/auth/login", {"email": "demo@studysync.app", "password": "Wrong12345"})
    call("GET /api/users/me/dashboard", "get", "/api/users/me/dashboard", headers=h)
    call("GET /api/groups", "get", "/api/groups?search=data&limit=2", headers=h)
    call("POST /api/groups", "post", "/api/groups", {"name": "Graph Theory Club", "description": "Weekly graph problems and mock interviews.", "subject": "Data Structures", "visibility": "public"}, h)
    call("POST /api/groups/{group_id}/resources", "post", "/api/groups/g1/resources", {"title": "Dijkstra walkthrough", "type": "link", "url": "https://example.com/dijkstra", "tags": ["graphs", "Shortest-Path"]}, h)
    call("POST /api/groups/{group_id}/resources (invalid)", "post", "/api/groups/g1/resources", {"title": "ab", "type": "link", "url": "javascript:alert(1)"}, h)
    call("GET /api/groups/{group_id}/sessions", "get", "/api/groups/g1/sessions", headers=h, keep=1)
    call("PUT /api/sessions/{session_id}/rsvp", "put", "/api/sessions/s1/rsvp", {"status": "going"}, h)
    call("GET /api/groups/{group_id} (private, not a member)", "get", "/api/groups/g7", headers=h)
    call("GET /api/notifications", "get", "/api/notifications", headers=h, keep=2)
    return out


def example_block(key, examples):
    if key not in examples:
        return ""
    body, status, data = examples[key]
    lines = ["", "**Example**", "", "```http", f"{key.split(' (')[0]}" + (f"   # {key.split(' (')[1].rstrip(')')}" if " (" in key else "")]
    if body is not None:
        lines += [json.dumps(body, indent=2)]
    shown = re.sub(r'("accessToken": ")[^"]{12}[^"]*', r"\1eyJhbGciOiJIUzI1NiJ9...", json.dumps(data, indent=2))
    lines += [f"-> {status}", shown[:1800], "```"]
    return "\n".join(lines)


def build_markdown(examples):
    out = ["# StudySync API reference", "",
           "Base URL (development): `http://localhost:5000`. Every endpoint lives under `/api`. All bodies are JSON.", "",
           "## Conventions", "",
           "- **Success:** `{ \"success\": true, \"data\": ... }`. Lists are returned as arrays (paged lists also send `X-Total-Count`); discovery returns `{ items, total, page, pages }`.",
           "- **Error:** `{ \"success\": false, \"message\": \"...\", \"errors\": { \"field\": \"message\" } }` (`errors` only for validation failures).",
           "- **Authentication:** `Authorization: Bearer <accessToken>`. Access tokens last 15 minutes. A refresh token (7 days, rotating) lives in an httpOnly cookie named `studysync_refresh` scoped to `/api/auth`; call `POST /api/auth/refresh` to get a new access token.",
           "- **Identifiers** are opaque strings. **Timestamps** are ISO 8601 UTC with a `Z` suffix.",
           "- **Rate limits:** 300 requests/minute per IP overall, 10/minute for register, login and refresh, 5 failed logins per 15 minutes per IP and email, 10/minute for join-by-code. Exceeding a limit returns 429 with `Retry-After`.", "",
           "## Status codes", "", "| Code | Meaning |", "|---|---|"]
    out += [f"| {code} | {text} |" for code, text in spec.ERROR_TEXT.items()]
    out += ["", "## Response models", ""] + [f"- `{name}` = `{shape}`" for name, shape in spec.MODELS.items()] + ["", "## Endpoints", ""]
    tags = []
    for e in spec.ENDPOINTS:
        if e[2] not in tags:
            tags.append(e[2])
    for tag in tags:
        out += [f"### {tag}", ""]
        for method, path, _tag, access, summary, body, query, status, returns, errors in [e for e in spec.ENDPOINTS if e[2] == tag]:
            out += [f"#### `{method} {path}`", "", summary, "", f"- **Access:** {access}", f"- **Success:** {status} returns `{returns}`"]
            all_errors = sorted(set(errors + ([401] if access != "Public" and "cookie" not in access else [])))
            if all_errors:
                out.append("- **Errors:** " + ", ".join(str(code) for code in all_errors))
            if query:
                out += ["", "| Query parameter | Type | Notes |", "|---|---|---|"] + [f"| `{n}` | {t} | {d} |" for n, t, d in query]
            if body:
                out += ["", "| Body field | Type | Required | Rules |", "|---|---|---|---|"] + [f"| `{f['name']}` | {f['type']} | {'yes' if f['required'] else 'no'} | {f['description']} |" for f in body]
            for key in (f"{method} {path}", f"{method} {path} (wrong)", f"{method} {path} (invalid)", f"{method} {path} (private, not a member)"):
                block = example_block(key, examples)
                if block:
                    out.append(block)
            out.append("")
    return "\n".join(out)


def build_openapi():
    paths = {}
    for method, path, tag, access, summary, body, query, status, returns, errors in spec.ENDPOINTS:
        op = {"tags": [tag], "summary": summary, "description": f"Access: {access}. Returns `{returns}`."}
        params = [{"name": m, "in": "path", "required": True, "schema": {"type": "string"}} for m in re.findall(r"{(\w+)}", path)]
        params += [{"name": n, "in": "query", "required": False, "description": d, "schema": {"type": {"integer": "integer", "boolean": "boolean"}.get(t, "string")}} for n, t, d in query]
        if params:
            op["parameters"] = params
        if body:
            props = {f["name"]: {"type": "array", "items": {"type": "string"}} if f["type"].endswith("[]") else {"type": f["type"], "description": f["description"]} for f in body}
            schema = {"type": "object", "properties": props}
            required = [f["name"] for f in body if f["required"]]
            if required:
                schema["required"] = required
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": schema}}}
        op["responses"] = {str(status): {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Success"}}}}}
        for code in sorted(set(errors + ([401] if access != "Public" and "cookie" not in access else []))):
            op["responses"][str(code)] = {"description": spec.ERROR_TEXT[code], "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
        if access not in ("Public", "Refresh cookie"):
            op["security"] = [{"bearerAuth": []}]
        paths.setdefault(path, {})[method.lower()] = op
    return {
        "openapi": "3.0.3",
        "info": {"title": "StudySync API", "version": "1.0.0", "description": "REST API for the StudySync collaborative study-group platform (Week 3)."},
        "servers": [{"url": "http://localhost:5000"}],
        "paths": paths,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
            "schemas": {
                "Success": {"type": "object", "properties": {"success": {"type": "boolean", "example": True}, "data": {}}},
                "Error": {"type": "object", "properties": {"success": {"type": "boolean", "example": False}, "message": {"type": "string"}, "errors": {"type": "object", "additionalProperties": {"type": "string"}}}},
            },
        },
    }


if __name__ == "__main__":
    examples = capture_examples()
    (ROOT / "docs" / "API.md").write_text(build_markdown(examples))
    (ROOT / "docs" / "openapi.yaml").write_text(yaml.safe_dump(build_openapi(), sort_keys=False, width=120, allow_unicode=True))
    print(f"Wrote docs/API.md ({len(spec.ENDPOINTS)} endpoints) and docs/openapi.yaml")
