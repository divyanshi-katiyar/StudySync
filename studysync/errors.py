"""One error type and one JSON error shape: { success: false, message, errors? }."""
import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger("studysync")

_MESSAGES = {
    400: "The request could not be understood.",
    404: "That endpoint does not exist.",
    405: "That method is not allowed on this endpoint.",
    413: "The request body is too large.",
    415: "Send the request body as JSON (Content-Type: application/json).",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str, errors: dict | None = None, headers: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.errors = errors or {}
        self.headers = headers or {}


def error_response(status: int, message: str, errors: dict | None = None, headers: dict | None = None):
    body = {"success": False, "message": message}
    if errors:
        body["errors"] = errors
    response = jsonify(body)
    response.status_code = status
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.status, err.message, err.errors, err.headers)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        status = err.code or 500
        return error_response(status, _MESSAGES.get(status, err.description or "Request failed."))

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # Never leak stack traces or SQL to the client; log them for the developer instead.
        log.exception("Unhandled error: %s", err)
        return error_response(500, "Something went wrong on our side. Please try again.")
