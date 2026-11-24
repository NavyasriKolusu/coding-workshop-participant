"""Team member CRUD Lambda handler."""

from typing import Any

from db import get_connection, parse_request, response


FIELDS = {
    "name": "name",
    "email": "email",
    "department": "department",
    "title": "title",
    "status": "status",
}
STATUSES = {"active", "inactive"}
MEMBER_SELECT = """
    SELECT tm.id, tm.name, tm.email, tm.department, tm.title, tm.status,
           COALESCE(SUM(a.allocation_percent), 0) AS allocation_total
    FROM team_members tm
    LEFT JOIN allocations a ON a.member_id = tm.id
"""


def _member_id(path: str) -> int | None:
    """Parse an optional team member id from the service path."""
    if path == "/":
        return None
    try:
        return int(path.strip("/"))
    except ValueError as error:
        raise ValueError("Team member id must be an integer") from error


def _validate(data: dict[str, Any], creating: bool = False) -> None:
    """Validate team member fields."""
    required = ("name", "email", "department")
    if creating and any(not str(data.get(field, "")).strip() for field in required):
        raise ValueError("Name, email, and department are required")
    if "name" in data and not str(data["name"]).strip():
        raise ValueError("Name cannot be empty")
    if "email" in data and "@" not in str(data["email"]):
        raise ValueError("Enter a valid email address")
    if "status" in data and data["status"] not in STATUSES:
        raise ValueError("Status must be active or inactive")
    if not creating and not any(field in data for field in FIELDS):
        raise ValueError("At least one team member field is required")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown team member fields: {', '.join(sorted(unknown))}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List, create, update, retrieve, or delete team members."""
    del context
    try:
        method, path, body, query = parse_request(event, "team_members")
        if method == "OPTIONS":
            return response({}, 200)
        member_id = _member_id(path)

        with get_connection().cursor() as cursor:
            if method == "GET":
                conditions = ["TRUE"]
                values: list[Any] = []
                if member_id is not None:
                    conditions.append("tm.id = %s")
                    values.append(member_id)
                search = (query.get("search") or query.get("name") or "").strip()
                if search:
                    conditions.append("tm.name ILIKE %s")
                    values.append(f"%{search}%")
                if query.get("department"):
                    conditions.append("tm.department ILIKE %s")
                    values.append(f"%{query['department']}%")
                if query.get("status"):
                    conditions.append("tm.status = %s")
                    values.append(query["status"])
                cursor.execute(
                    f"{MEMBER_SELECT} WHERE {' AND '.join(conditions)} "
                    "GROUP BY tm.id ORDER BY tm.name",
                    values,
                )
                if member_id is not None:
                    member = cursor.fetchone()
                    return response(member) if member else response({"error": "Team member not found"}, 404)
                return response(cursor.fetchall())

            if method == "POST" and member_id is None:
                _validate(body, creating=True)
                cursor.execute(
                    """
                    INSERT INTO team_members (name, email, department, title, status)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        body["name"].strip(),
                        body["email"].strip().lower(),
                        body["department"].strip(),
                        body.get("title", ""),
                        body.get("status", "active"),
                    ),
                )
                new_id = cursor.fetchone()["id"]
                cursor.execute(
                    f"{MEMBER_SELECT} WHERE tm.id = %s GROUP BY tm.id",
                    (new_id,),
                )
                return response(cursor.fetchone(), 201)

            if method == "PUT" and member_id is not None:
                _validate(body)
                fields = {key: value for key, value in body.items() if key in FIELDS}
                assignments = ", ".join(f"{FIELDS[key]} = %s" for key in fields)
                cursor.execute(
                    f"UPDATE team_members SET {assignments} WHERE id = %s RETURNING id",
                    (*fields.values(), member_id),
                )
                if cursor.fetchone() is None:
                    return response({"error": "Team member not found"}, 404)
                cursor.execute(
                    f"{MEMBER_SELECT} WHERE tm.id = %s GROUP BY tm.id",
                    (member_id,),
                )
                return response(cursor.fetchone())

            if method == "DELETE" and member_id is not None:
                cursor.execute(
                    "DELETE FROM team_members WHERE id = %s RETURNING id",
                    (member_id,),
                )
                if cursor.fetchone() is None:
                    return response({"error": "Team member not found"}, 404)
                return response({"status": "deleted"})

        return response({"error": "Method or path not allowed"}, 405)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
