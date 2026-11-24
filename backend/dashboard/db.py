"""Shared PostgreSQL and Lambda event helpers."""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any


_connection: Any = None


def get_connection() -> Any:
    """Return a warm, autocommit PostgreSQL connection."""
    global _connection
    if _connection is None or _connection.closed:
        import psycopg
        from psycopg.rows import dict_row

        _connection = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASS", "postgres123"),
            dbname=os.getenv("POSTGRES_NAME", "postgres"),
            autocommit=True,
            row_factory=dict_row,
        )
    return _connection


def json_default(value: Any) -> Any:
    """Convert PostgreSQL decimal and date values to JSON-compatible values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def response(payload: Any, status_code: int = 200) -> dict[str, Any]:
    """Create a JSON Lambda response with browser-friendly CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(payload, default=json_default),
    }


def parse_request(event: dict[str, Any], service: str) -> tuple[str, str, dict[str, Any], dict[str, str]]:
    """Read method, service-relative path, JSON body, and query from a Lambda event."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    parts = [part for part in event.get("rawPath", "/").split("/") if part]
    if parts and parts[0] == "api":
        parts.pop(0)
    if parts and parts[0] == service:
        parts.pop(0)
    path = "/" + "/".join(parts)

    body_text = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body_text = base64.b64decode(body_text).decode("utf-8")
    body = json.loads(body_text) if body_text else {}
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    query = event.get("queryStringParameters") or {}
    return method, path, body, query


def issue_token(user: dict[str, Any]) -> str:
    """Create a signed, expiring authentication token for a user."""
    payload = {
        "username": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + 12 * 60 * 60,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signature = hmac.new(_token_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    signed = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded}.{signed}"


def _token_secret() -> bytes:
    """Get the signing secret from configuration or the database password."""
    secret = os.getenv("AUTH_SECRET") or os.getenv("POSTGRES_PASS", "postgres123")
    return secret.encode("utf-8")


def _decode_token(token: str) -> dict[str, Any]:
    """Validate a token signature and expiry, returning its claims."""
    try:
        encoded, provided_signature = token.split(".", 1)
        expected_signature = hmac.new(
            _token_secret(), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        padded_signature = provided_signature + "=" * (-len(provided_signature) % 4)
        signature = base64.urlsafe_b64decode(padded_signature.encode("ascii"))
        if not hmac.compare_digest(expected_signature, signature):
            raise PermissionError("Invalid authentication token")
        padded_payload = encoded + "=" * (-len(encoded) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded_payload.encode("ascii")))
        if not isinstance(claims, dict) or int(claims.get("exp", 0)) <= int(time.time()):
            raise PermissionError("Authentication token has expired")
        if not claims.get("username") or not claims.get("role"):
            raise PermissionError("Invalid authentication token")
        return claims
    except PermissionError:
        raise
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermissionError("Invalid authentication token") from error


def current_user(event: dict[str, Any]) -> dict[str, Any]:
    """Validate the bearer token and read the user's current database role."""
    headers = event.get("headers") or {}
    authorization = next(
        (value for key, value in headers.items() if key.lower() == "authorization"),
        "",
    )
    scheme, _, token = authorization.partition(" ")
    if not token and os.getenv("IS_LOCAL", "false").lower() == "true":
        # The local workshop proxy forwards Content-Type but drops Authorization.
        content_type = next(
            (value for key, value in headers.items() if key.lower() == "content-type"),
            "",
        )
        token = next(
            (
                part.split("=", 1)[1]
                for part in content_type.split(";")
                if part.strip().startswith("acme-token=")
            ),
            "",
        )
        scheme = "bearer" if token else scheme
    if scheme.lower() != "bearer" or not token:
        raise PermissionError("Authentication required")
    claims = _decode_token(token)
    with get_connection().cursor() as cursor:
        cursor.execute(
            "SELECT id, username, role, name FROM users WHERE username = %s",
            (claims["username"],),
        )
        user = cursor.fetchone()
    if user is None:
        raise PermissionError("Authentication required")
    return user


def require_user(event: dict[str, Any], allowed_roles: set[str]) -> dict[str, Any] | None:
    """Return a JSON error response when the user lacks required access."""
    try:
        user = current_user(event)
    except PermissionError as error:
        return response({"error": str(error)}, 401)
    if user["role"] not in allowed_roles:
        return response({"error": "You do not have permission to perform this action"}, 403)
    return None


def authorize_request(event: dict[str, Any], method: str) -> dict[str, Any] | None:
    """Allow all roles to read and only managers/admins to change records."""
    roles = {"admin", "manager", "member"} if method == "GET" else {"admin", "manager"}
    return require_user(event, roles)
