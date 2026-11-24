"""Shared PostgreSQL and Lambda event helpers."""

import base64
import json
import os
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
    query = event.get("queryStringParameters") or {}
    return method, path, body, query
