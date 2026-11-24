"""Allocation CRUD Lambda handler."""

from typing import Any

from db import authorize_request, get_connection, parse_request, response


FIELDS = {
    "member_id": "member_id",
    "project_id": "project_id",
    "allocation_percent": "allocation_percent",
}
ALLOCATION_SELECT = """
    SELECT a.id, a.member_id, tm.name AS member_name, tm.department,
           a.project_id, p.name AS project_name, p.status AS project_status,
           a.allocation_percent,
           SUM(a.allocation_percent) OVER (PARTITION BY a.member_id)
               AS member_allocation_total
    FROM allocations a
    JOIN team_members tm ON tm.id = a.member_id
    JOIN projects p ON p.id = a.project_id
"""


def _allocation_id(path: str) -> int | None:
    """Parse an optional allocation id from the service path."""
    if path == "/":
        return None
    try:
        return int(path.strip("/"))
    except ValueError as error:
        raise ValueError("Allocation id must be an integer") from error


def _validate(data: dict[str, Any], creating: bool = False) -> None:
    """Validate allocation fields and percentage bounds."""
    required = ("member_id", "project_id", "allocation_percent")
    if creating and any(field not in data for field in required):
        raise ValueError("Member, project, and allocation percentage are required")
    if not creating and not any(field in data for field in FIELDS):
        raise ValueError("At least one allocation field is required")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown allocation fields: {', '.join(sorted(unknown))}")
    try:
        for field in ("member_id", "project_id"):
            if field in data and int(data[field]) < 1:
                raise ValueError(f"{field} must be a positive integer")
        if "allocation_percent" in data:
            percent = float(data["allocation_percent"])
            if percent <= 0 or percent > 100:
                raise ValueError("Allocation percentage must be greater than 0 and at most 100")
    except (TypeError, ValueError) as error:
        if isinstance(error, ValueError) and str(error).startswith(("member_id", "project_id", "Allocation")):
            raise
        raise ValueError("Member and project ids must be integers; percentage must be numeric") from error


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List, create, update, retrieve, or delete allocations."""
    del context
    try:
        method, path, body, query = parse_request(event, "allocations")
        if method == "OPTIONS":
            return response({}, 200)
        if method in {"GET", "POST", "PUT", "DELETE"}:
            access_error = authorize_request(event, method)
            if access_error:
                return access_error
        allocation_id = _allocation_id(path)

        with get_connection().cursor() as cursor:
            if method == "GET":
                conditions = ["TRUE"]
                values: list[Any] = []
                if allocation_id is not None:
                    conditions.append("a.id = %s")
                    values.append(allocation_id)
                search = (query.get("search") or query.get("name") or "").strip()
                if search:
                    conditions.append("(tm.name ILIKE %s OR p.name ILIKE %s)")
                    values.extend((f"%{search}%", f"%{search}%"))
                if query.get("department"):
                    conditions.append("tm.department ILIKE %s")
                    values.append(f"%{query['department']}%")
                if query.get("status"):
                    conditions.append("p.status = %s")
                    values.append(query["status"])
                cursor.execute(
                    f"{ALLOCATION_SELECT} WHERE {' AND '.join(conditions)} ORDER BY tm.name, p.name",
                    values,
                )
                if allocation_id is not None:
                    allocation = cursor.fetchone()
                    return response(allocation) if allocation else response({"error": "Allocation not found"}, 404)
                return response(cursor.fetchall())

            if method == "POST" and allocation_id is None:
                _validate(body, creating=True)
                cursor.execute(
                    """
                    INSERT INTO allocations (member_id, project_id, allocation_percent)
                    VALUES (%s, %s, %s) RETURNING id
                    """,
                    (int(body["member_id"]), int(body["project_id"]), body["allocation_percent"]),
                )
                new_id = cursor.fetchone()["id"]
                cursor.execute(f"{ALLOCATION_SELECT} WHERE a.id = %s", (new_id,))
                return response(cursor.fetchone(), 201)

            if method == "PUT" and allocation_id is not None:
                _validate(body)
                fields = {key: value for key, value in body.items() if key in FIELDS}
                assignments = ", ".join(f"{FIELDS[key]} = %s" for key in fields)
                values = [
                    int(value) if key in ("member_id", "project_id") else value
                    for key, value in fields.items()
                ]
                cursor.execute(
                    f"UPDATE allocations SET {assignments} WHERE id = %s RETURNING id",
                    (*values, allocation_id),
                )
                if cursor.fetchone() is None:
                    return response({"error": "Allocation not found"}, 404)
                cursor.execute(
                    f"{ALLOCATION_SELECT} WHERE a.id = %s",
                    (allocation_id,),
                )
                return response(cursor.fetchone())

            if method == "DELETE" and allocation_id is not None:
                cursor.execute("DELETE FROM allocations WHERE id = %s RETURNING id", (allocation_id,))
                if cursor.fetchone() is None:
                    return response({"error": "Allocation not found"}, 404)
                return response({"status": "deleted"})

        return response({"error": "Method or path not allowed"}, 405)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
