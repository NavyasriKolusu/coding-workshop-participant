"""Authentication and administrator user-management Lambda handler."""

import hashlib
import hmac
import os
from typing import Any

from db import current_user, get_connection, issue_token, parse_request, require_user, response


ROLES = {"admin", "manager", "member"}
HASH_ROUNDS = 240_000
USER_FIELDS = {"username", "name", "role", "password"}
PUBLIC_USER_COLUMNS = "id, username, role, name, created_at"


def _hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, HASH_ROUNDS
    )
    return f"pbkdf2_sha256${HASH_ROUNDS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against the stored versioned PBKDF2 hash."""
    try:
        algorithm, rounds, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(calculated.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _user_id(path: str) -> int | None:
    """Parse an optional administrator user id from the service path."""
    if path == "/users":
        return None
    if not path.startswith("/users/"):
        raise ValueError("Unknown authentication path")
    try:
        return int(path.removeprefix("/users/"))
    except ValueError as error:
        raise ValueError("User id must be an integer") from error


def _validate_user(data: dict[str, Any], creating: bool = False) -> None:
    """Validate user profile and password fields."""
    if creating and any(not str(data.get(field, "")).strip() for field in ("username", "name", "password")):
        raise ValueError("Username, name, and password are required")
    if creating and data.get("role") not in ROLES:
        raise ValueError("Role must be admin, manager, or member")
    if "name" in data and not str(data["name"]).strip():
        raise ValueError("Name cannot be empty")
    if "username" in data and not str(data["username"]).strip():
        raise ValueError("Username cannot be empty")
    if "role" in data and data["role"] not in ROLES:
        raise ValueError("Role must be admin, manager, or member")
    if "password" in data and len(str(data["password"])) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not creating and not any(field in data for field in USER_FIELDS):
        raise ValueError("At least one user field is required")
    unknown = set(data) - USER_FIELDS
    if unknown:
        raise ValueError(f"Unknown user fields: {', '.join(sorted(unknown))}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Authenticate users and allow admins to manage accounts."""
    del context
    try:
        method, path, body, query = parse_request(event, "auth")
        if method == "OPTIONS":
            return response({}, 200)

        if path == "/login" and method == "POST":
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
            if not username or not password:
                return response({"error": "Username and password are required"}, 400)
            with get_connection().cursor() as cursor:
                cursor.execute(
                    f"SELECT {PUBLIC_USER_COLUMNS}, password_hash FROM users WHERE username = %s",
                    (username,),
                )
                user = cursor.fetchone()
            if user is None or not _verify_password(password, user["password_hash"]):
                return response({"error": "Invalid username or password"}, 401)
            safe_user = {key: value for key, value in user.items() if key != "password_hash"}
            return response({"token": issue_token(user), "user": safe_user})

        if path == "/me" and method == "GET":
            try:
                return response(current_user(event))
            except PermissionError as error:
                return response({"error": str(error)}, 401)

        if path == "/users" or path.startswith("/users/"):
            access_error = require_user(event, {"admin"})
            if access_error:
                return access_error
            user_id = _user_id(path)

            with get_connection().cursor() as cursor:
                if method == "GET" and user_id is None:
                    conditions = ["TRUE"]
                    values: list[Any] = []
                    search = (query.get("search") or query.get("name") or "").strip()
                    if search:
                        conditions.append("(name ILIKE %s OR username ILIKE %s)")
                        values.extend((f"%{search}%", f"%{search}%"))
                    if query.get("status"):
                        conditions.append("role = %s")
                        values.append(query["status"])
                    cursor.execute(
                        f"SELECT {PUBLIC_USER_COLUMNS} FROM users "
                        f"WHERE {' AND '.join(conditions)} ORDER BY name",
                        values,
                    )
                    return response(cursor.fetchall())

                if method == "POST" and user_id is None:
                    _validate_user(body, creating=True)
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, role, name)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, username, role, name, created_at
                        """,
                        (
                            body["username"].strip(),
                            _hash_password(body["password"]),
                            body["role"],
                            body["name"].strip(),
                        ),
                    )
                    return response(cursor.fetchone(), 201)

                if method == "PUT" and user_id is not None:
                    _validate_user(body)
                    fields = {key: value for key, value in body.items() if key in USER_FIELDS}
                    assignments: list[str] = []
                    values: list[Any] = []
                    for key, value in fields.items():
                        column = "password_hash" if key == "password" else key
                        assignments.append(f"{column} = %s")
                        values.append(_hash_password(value) if key == "password" else value)
                    cursor.execute(
                        f"UPDATE users SET {', '.join(assignments)} WHERE id = %s "
                        "RETURNING id, username, role, name, created_at",
                        (*values, user_id),
                    )
                    user = cursor.fetchone()
                    return response(user) if user else response({"error": "User not found"}, 404)

                if method == "DELETE" and user_id is not None:
                    actor = current_user(event)
                    if actor["id"] == user_id:
                        return response({"error": "You cannot delete your own account"}, 400)
                    cursor.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
                    if cursor.fetchone() is None:
                        return response({"error": "User not found"}, 404)
                    return response({"status": "deleted"})

            return response({"error": "Method or path not allowed"}, 405)

        return response({"error": "Authentication route not found"}, 404)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
