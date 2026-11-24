"""Deliverable CRUD and dependency Lambda handler."""

from typing import Any

from db import authorize_request, get_connection, parse_request, response


FIELDS = {
    "project_id": "project_id",
    "name": "name",
    "description": "description",
    "status": "status",
    "progress": "progress",
    "due_date": "due_date",
    "assigned_to": "assigned_to",
}
STATUSES = {"not_started", "in_progress", "completed"}
DELIVERABLE_SELECT = """
    SELECT d.id, d.project_id, p.name AS project_name,
           p.department AS project_department, d.name, d.description,
           d.status, d.progress, d.due_date, d.assigned_to,
           tm.name AS assigned_member_name,
           ARRAY(
               SELECT dependency.depends_on_id
               FROM deliverable_dependencies dependency
               WHERE dependency.deliverable_id = d.id
               ORDER BY dependency.depends_on_id
           ) AS depends_on_ids,
           ARRAY(
               SELECT parent.name
               FROM deliverable_dependencies dependency
               JOIN deliverables parent ON parent.id = dependency.depends_on_id
               WHERE dependency.deliverable_id = d.id
               ORDER BY parent.name
           ) AS dependency_names
    FROM deliverables d
    JOIN projects p ON p.id = d.project_id
    LEFT JOIN team_members tm ON tm.id = d.assigned_to
"""


def _deliverable_id(path: str) -> int | None:
    """Parse an optional deliverable id from the service path."""
    if path == "/":
        return None
    try:
        return int(path.strip("/"))
    except ValueError as error:
        raise ValueError("Deliverable id must be an integer") from error


def _validate(data: dict[str, Any], creating: bool = False) -> list[int]:
    """Validate deliverable fields and normalize dependency ids."""
    if creating and (not data.get("name") or not data.get("project_id")):
        raise ValueError("Project and deliverable name are required")
    if "name" in data and not str(data["name"]).strip():
        raise ValueError("Deliverable name cannot be empty")
    if "status" in data and data["status"] not in STATUSES:
        raise ValueError("Status must be not_started, in_progress, or completed")
    if "progress" in data and not 0 <= int(data["progress"]) <= 100:
        raise ValueError("Progress must be between 0 and 100")
    if not creating and not any(field in data for field in FIELDS) and "depends_on" not in data:
        raise ValueError("At least one deliverable field is required")
    unknown = set(data) - set(FIELDS) - {"depends_on"}
    if unknown:
        raise ValueError(f"Unknown deliverable fields: {', '.join(sorted(unknown))}")

    raw_dependencies = data.get("depends_on", [])
    if not isinstance(raw_dependencies, list):
        raise ValueError("depends_on must be a list of deliverable ids")
    try:
        dependencies = [int(value) for value in raw_dependencies]
    except (TypeError, ValueError) as error:
        raise ValueError("Dependency ids must be integers") from error
    if any(value < 1 for value in dependencies):
        raise ValueError("Dependency ids must be positive integers")
    if len(set(dependencies)) != len(dependencies):
        raise ValueError("Dependency ids must be unique")
    return dependencies


def _validate_dependencies(cursor: Any, dependencies: list[int], current_id: int | None = None) -> None:
    """Ensure dependencies exist and cannot introduce a cycle."""
    if current_id is not None and current_id in dependencies:
        raise ValueError("A deliverable cannot depend on itself")
    if dependencies:
        cursor.execute("SELECT id FROM deliverables WHERE id = ANY(%s)", (dependencies,))
        found = {row["id"] for row in cursor.fetchall()}
        if found != set(dependencies):
            raise ValueError("One or more dependency deliverables do not exist")

    if current_id is None or not dependencies:
        return
    cursor.execute(
        """
        SELECT deliverable_id, depends_on_id
        FROM deliverable_dependencies
        WHERE deliverable_id <> %s
        """,
        (current_id,),
    )
    graph: dict[int, set[int]] = {}
    for row in cursor.fetchall():
        graph.setdefault(row["deliverable_id"], set()).add(row["depends_on_id"])
    for dependency in dependencies:
        pending = [dependency]
        visited: set[int] = set()
        while pending:
            node = pending.pop()
            if node == current_id:
                raise ValueError("This dependency would create a cycle")
            if node not in visited:
                visited.add(node)
                pending.extend(graph.get(node, set()))


def _fetch_one(cursor: Any, deliverable_id: int) -> Any:
    """Fetch one deliverable with its dependency names."""
    cursor.execute(f"{DELIVERABLE_SELECT} WHERE d.id = %s", (deliverable_id,))
    return cursor.fetchone()


def _save_dependencies(cursor: Any, deliverable_id: int, dependencies: list[int]) -> None:
    """Replace the dependency links for one deliverable."""
    cursor.execute(
        "DELETE FROM deliverable_dependencies WHERE deliverable_id = %s",
        (deliverable_id,),
    )
    for dependency in dependencies:
        cursor.execute(
            """
            INSERT INTO deliverable_dependencies (deliverable_id, depends_on_id)
            VALUES (%s, %s)
            """,
            (deliverable_id, dependency),
        )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List, create, update, retrieve, or delete deliverables."""
    del context
    try:
        method, path, body, query = parse_request(event, "deliverables")
        if method == "OPTIONS":
            return response({}, 200)
        if method in {"GET", "POST", "PUT", "DELETE"}:
            access_error = authorize_request(event, method)
            if access_error:
                return access_error
        deliverable_id = _deliverable_id(path)

        with get_connection().cursor() as cursor:
            if method == "GET":
                conditions = ["TRUE"]
                values: list[Any] = []
                if deliverable_id is not None:
                    conditions.append("d.id = %s")
                    values.append(deliverable_id)
                search = (query.get("search") or query.get("name") or "").strip()
                if search:
                    conditions.append("d.name ILIKE %s")
                    values.append(f"%{search}%")
                if query.get("status"):
                    conditions.append("d.status = %s")
                    values.append(query["status"])
                if query.get("department"):
                    conditions.append("p.department ILIKE %s")
                    values.append(f"%{query['department']}%")
                if query.get("project_id"):
                    conditions.append("d.project_id = %s")
                    values.append(query["project_id"])
                cursor.execute(
                    f"{DELIVERABLE_SELECT} WHERE {' AND '.join(conditions)} ORDER BY d.due_date NULLS LAST, d.id",
                    values,
                )
                if deliverable_id is not None:
                    deliverable = cursor.fetchone()
                    return response(deliverable) if deliverable else response({"error": "Deliverable not found"}, 404)
                return response(cursor.fetchall())

            if method == "POST" and deliverable_id is None:
                dependencies = _validate(body, creating=True)
                _validate_dependencies(cursor, dependencies)
                cursor.execute(
                    """
                    INSERT INTO deliverables
                        (project_id, name, description, status, progress, due_date, assigned_to)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        int(body["project_id"]),
                        body["name"].strip(),
                        body.get("description", ""),
                        body.get("status", "not_started"),
                        int(body.get("progress", 0)),
                        body.get("due_date") or None,
                        int(body["assigned_to"]) if body.get("assigned_to") else None,
                    ),
                )
                new_id = cursor.fetchone()["id"]
                _save_dependencies(cursor, new_id, dependencies)
                return response(_fetch_one(cursor, new_id), 201)

            if method == "PUT" and deliverable_id is not None:
                dependencies = _validate(body)
                if "depends_on" in body:
                    _validate_dependencies(cursor, dependencies, deliverable_id)
                fields = {key: value for key, value in body.items() if key in FIELDS}
                if fields:
                    assignments = ", ".join(f"{FIELDS[key]} = %s" for key in fields)
                    values = []
                    for key, value in fields.items():
                        if key in ("project_id", "progress"):
                            value = int(value)
                        elif key == "assigned_to":
                            value = int(value) if value else None
                        elif key == "due_date":
                            value = value or None
                        values.append(value)
                    cursor.execute(
                        f"UPDATE deliverables SET {assignments} WHERE id = %s RETURNING id",
                        (*values, deliverable_id),
                    )
                    if cursor.fetchone() is None:
                        return response({"error": "Deliverable not found"}, 404)
                elif _fetch_one(cursor, deliverable_id) is None:
                    return response({"error": "Deliverable not found"}, 404)
                if "depends_on" in body:
                    _save_dependencies(cursor, deliverable_id, dependencies)
                return response(_fetch_one(cursor, deliverable_id))

            if method == "DELETE" and deliverable_id is not None:
                cursor.execute("DELETE FROM deliverables WHERE id = %s RETURNING id", (deliverable_id,))
                if cursor.fetchone() is None:
                    return response({"error": "Deliverable not found"}, 404)
                return response({"status": "deleted"})

        return response({"error": "Method or path not allowed"}, 405)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
