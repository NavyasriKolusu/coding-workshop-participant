"""Budget entry CRUD Lambda handler."""

import math
from typing import Any

from db import get_connection, parse_request, response


FIELDS = {
    "project_id": "project_id",
    "category": "category",
    "description": "description",
    "entry_type": "entry_type",
    "amount": "amount",
    "entry_date": "entry_date",
}
ENTRY_TYPES = {"planned", "spent"}
ENTRY_SELECT = """
    SELECT b.id, b.project_id, p.name AS project_name,
           p.department AS department, b.category, b.description,
           b.entry_type, b.amount, b.entry_date
    FROM budget_entries b
    JOIN projects p ON p.id = b.project_id
"""


def _entry_id(path: str) -> int | None:
    """Parse an optional budget entry id from the service path."""
    if path == "/":
        return None
    try:
        return int(path.strip("/"))
    except ValueError as error:
        raise ValueError("Budget entry id must be an integer") from error


def _validate(data: dict[str, Any], creating: bool = False) -> None:
    """Validate budget entry fields and amounts."""
    if creating:
        required = ("project_id", "category", "entry_type", "amount")
        if any(field not in data for field in required):
            raise ValueError("Project, category, type, and amount are required")
    if "category" in data and not str(data["category"]).strip():
        raise ValueError("Category cannot be empty")
    if "entry_type" in data and data["entry_type"] not in ENTRY_TYPES:
        raise ValueError("Entry type must be planned or spent")
    if "project_id" in data:
        try:
            if int(data["project_id"]) < 1:
                raise ValueError("Project id must be a positive integer")
        except (TypeError, ValueError) as error:
            if str(error).startswith("Project id"):
                raise
            raise ValueError("Project id must be a positive integer") from error
    if "amount" in data:
        try:
            amount = float(data["amount"])
        except (TypeError, ValueError) as error:
            raise ValueError("Amount must be a number") from error
        if not math.isfinite(amount):
            raise ValueError("Amount must be a finite number")
        if amount < 0:
            raise ValueError("Amount cannot be negative")
    if not creating and not any(field in data for field in FIELDS):
        raise ValueError("At least one budget entry field is required")
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown budget entry fields: {', '.join(sorted(unknown))}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List, create, update, retrieve, or delete budget entries."""
    del context
    try:
        method, path, body, query = parse_request(event, "budget_entries")
        if method == "OPTIONS":
            return response({}, 200)
        entry_id = _entry_id(path)

        with get_connection().cursor() as cursor:
            if method == "GET":
                conditions = ["TRUE"]
                values: list[Any] = []
                if entry_id is not None:
                    conditions.append("b.id = %s")
                    values.append(entry_id)
                search = (query.get("search") or query.get("name") or "").strip()
                if search:
                    conditions.append("(b.category ILIKE %s OR p.name ILIKE %s)")
                    values.extend((f"%{search}%", f"%{search}%"))
                if query.get("status"):
                    conditions.append("b.entry_type = %s")
                    values.append(query["status"])
                if query.get("department"):
                    conditions.append("p.department ILIKE %s")
                    values.append(f"%{query['department']}%")
                cursor.execute(
                    f"{ENTRY_SELECT} WHERE {' AND '.join(conditions)} ORDER BY b.entry_date DESC, b.id",
                    values,
                )
                if entry_id is not None:
                    entry = cursor.fetchone()
                    return response(entry) if entry else response({"error": "Budget entry not found"}, 404)
                return response(cursor.fetchall())

            if method == "POST" and entry_id is None:
                _validate(body, creating=True)
                cursor.execute(
                    """
                    INSERT INTO budget_entries
                        (project_id, category, description, entry_type, amount, entry_date)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                    RETURNING id
                    """,
                    (
                        int(body["project_id"]),
                        body["category"].strip(),
                        body.get("description", ""),
                        body["entry_type"],
                        body["amount"],
                        body.get("entry_date") or None,
                    ),
                )
                new_id = cursor.fetchone()["id"]
                cursor.execute(f"{ENTRY_SELECT} WHERE b.id = %s", (new_id,))
                return response(cursor.fetchone(), 201)

            if method == "PUT" and entry_id is not None:
                _validate(body)
                fields = {key: value for key, value in body.items() if key in FIELDS}
                assignments = ", ".join(f"{FIELDS[key]} = %s" for key in fields)
                values = [
                    int(value) if key == "project_id" else value
                    for key, value in fields.items()
                ]
                cursor.execute(
                    f"UPDATE budget_entries SET {assignments} WHERE id = %s RETURNING id",
                    (*values, entry_id),
                )
                if cursor.fetchone() is None:
                    return response({"error": "Budget entry not found"}, 404)
                cursor.execute(f"{ENTRY_SELECT} WHERE b.id = %s", (entry_id,))
                return response(cursor.fetchone())

            if method == "DELETE" and entry_id is not None:
                cursor.execute("DELETE FROM budget_entries WHERE id = %s RETURNING id", (entry_id,))
                if cursor.fetchone() is None:
                    return response({"error": "Budget entry not found"}, 404)
                return response({"status": "deleted"})

        return response({"error": "Method or path not allowed"}, 405)
    except ValueError as error:
        return response({"error": str(error)}, 400)
    except Exception as error:
        return response({"error": str(error)}, 500)
