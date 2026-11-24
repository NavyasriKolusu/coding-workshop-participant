"""Project CRUD Lambda handler."""

from typing import Any

from db import get_connection, parse_request, response


PROJECT_FIELDS = {
    "name": "name",
    "description": "description",
    "status": "status",
    "department": "department",
    "start_date": "start_date",
    "end_date": "end_date",
}
PROJECT_STATUSES = {"planning", "active", "on_hold", "completed"}
PROJECT_COLUMNS = "id, name, description, status, department, start_date, end_date"


def _project_id(path: str) -> int | None:
    """Parse an optional project id from the service-relative path."""
    if path == "/":
        return None
    try:
        return int(path.strip("/"))
    except ValueError as error:
        raise ValueError("Project id must be an integer") from error


def _validate(data: dict[str, Any], creating: bool = False) -> None:
    """Validate project fields before writing to PostgreSQL."""
    if creating and not str(data.get("name", "")).strip():
        raise ValueError("Project name is required")
    if "name" in data and not str(data["name"]).strip():
        raise ValueError("Project name cannot be empty")
    if "status" in data and data["status"] not in PROJECT_STATUSES:
        raise ValueError("Status must be planning, active, on_hold, or completed")
    if not creating and not any(field in data for field in PROJECT_FIELDS):
        raise ValueError("At least one project field is required")
    unknown = set(data) - set(PROJECT_FIELDS)
    if unknown:
        raise ValueError(f"Unknown project fields: {', '.join(sorted(unknown))}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List, create, update, retrieve, or delete projects."""
    del context
    try:
        method, path, body, query = parse_request(event, "projects")
        if method == "OPTIONS":
            return response({}, 200)
        project_id = _project_id(path)

        with get_connection().cursor() as cursor:
            if method == "GET" and project_id is None:
                conditions = ["TRUE"]
                values: list[Any] = []
                search = (query.get("search") or query.get("name") or "").strip()
                if search:
                    conditions.append("name ILIKE %s")
                    values.append(f"%{search}%")
                if query.get("status"):
                    conditions.append("status = %s")
                    values.append(query["status"])
                if query.get("department"):
                    conditions.append("department ILIKE %s")
                    values.append(f"%{query['department']}%")
                cursor.execute(
                    f"SELECT {PROJECT_COLUMNS} FROM projects WHERE {' AND '.join(conditions)} ORDER BY id",
                    values,
                )
                return response(cursor.fetchall())

            if method == "GET" and project_id is not None:
                cursor.execute(
                    f"SELECT {PROJECT_COLUMNS} FROM projects WHERE id = %s",
                    (project_id,),
                )
                project = cursor.fetchone()
                return response(project, 200) if project else response({"error": "Project not found"}, 404)

            if method == "POST" and project_id is None:
                _validate(body, creating=True)
                cursor.execute(
                    f"""
                    INSERT INTO projects
                        (name, description, status, department, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING {PROJECT_COLUMNS}
                    """,
                    (
                        body["name"].strip(),
                        body.get("description", ""),
                        body.get("status", "planning"),
                        body.get("department", ""),
                        body.get("start_date") or None,
                        body.get("end_date") or None,
                    ),
                )
                return response(cursor.fetchone(), 201)

            if method == "PUT" and project_id is not None:
                _validate(body)
                fields = {key: value for key, value in body.items() if key in PROJECT_FIELDS}
                assignments = ", ".join(f"{PROJECT_FIELDS[key]} = %s" for key in fields)
                cursor.execute(
                    f"""
                    UPDATE projects SET {assignments}
                    WHERE id = %s RETURNING {PROJECT_COLUMNS}
                    """,
                    (*fields.values(), project_id),
                )
                project = cursor.fetchone()
                return response(project) if project else response({"error": "Project not found"}, 404)

            if method == "DELETE" and project_id is not None:
                cursor.execute("DELETE FROM projects WHERE id = %s RETURNING id", (project_id,))
                if cursor.fetchone() is None:
                    return response({"error": "Project not found"}, 404)
                return response({"status": "deleted"})

        return response({"error": "Method or path not allowed"}, 405)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
