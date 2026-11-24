"""Database setup Lambda handler."""

import hashlib
import os
from datetime import date, timedelta
from typing import Any

from db import get_connection, parse_request, response


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'member')),
        name TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS team_members (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        department TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'planning'
            CHECK (status IN ('planning', 'active', 'on_hold', 'completed')),
        department TEXT NOT NULL DEFAULT '',
        start_date DATE,
        end_date DATE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deliverables (
        id SERIAL PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'not_started'
            CHECK (status IN ('not_started', 'in_progress', 'completed')),
        progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
        due_date DATE,
        assigned_to INTEGER REFERENCES team_members(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deliverable_dependencies (
        deliverable_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
        depends_on_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
        PRIMARY KEY (deliverable_id, depends_on_id),
        CHECK (deliverable_id <> depends_on_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS allocations (
        id SERIAL PRIMARY KEY,
        member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        allocation_percent NUMERIC(5, 2) NOT NULL
            CHECK (allocation_percent > 0 AND allocation_percent <= 100),
        UNIQUE (member_id, project_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS budget_entries (
        id SERIAL PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        entry_type TEXT NOT NULL CHECK (entry_type IN ('planned', 'spent')),
        amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
        entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


def _password_hash(password: str) -> str:
    """Create the versioned PBKDF2 password format used by the auth service."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def _seed_samples(cursor: Any) -> None:
    """Insert demo data into tables that are still empty."""
    cursor.execute("SELECT COUNT(*) AS count FROM users")
    if cursor.fetchone()["count"] == 0:
        for username, password, role, name in (
            ("admin", "admin123", "admin", "Alex Admin"),
            ("manager", "manager123", "manager", "Morgan Manager"),
            ("member", "member123", "member", "Mia Member"),
        ):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, name) VALUES (%s, %s, %s, %s)",
                (username, _password_hash(password), role, name),
            )

    cursor.execute("SELECT COUNT(*) AS count FROM team_members")
    if cursor.fetchone()["count"] == 0:
        for member in (
            ("Mia Member", "mia@acme.example", "Engineering", "Software Engineer"),
            ("Noah Chen", "noah@acme.example", "Design", "Product Designer"),
            ("Ava Patel", "ava@acme.example", "Engineering", "Tech Lead"),
        ):
            cursor.execute(
                "INSERT INTO team_members (name, email, department, title) VALUES (%s, %s, %s, %s)",
                member,
            )

    today = date.today()
    cursor.execute("SELECT COUNT(*) AS count FROM projects")
    if cursor.fetchone()["count"] == 0:
        for project in (
            ("Customer Portal", "Modernize the customer experience.", "active", "Engineering", today - timedelta(days=30), today + timedelta(days=10)),
            ("Mobile App", "Launch the ACME mobile application.", "active", "Product", today - timedelta(days=20), today + timedelta(days=60)),
            ("Data Platform", "Build trusted analytics foundations.", "planning", "Engineering", today, today + timedelta(days=120)),
        ):
            cursor.execute(
                """
                INSERT INTO projects (name, description, status, department, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                project,
            )

    cursor.execute("SELECT COUNT(*) AS count FROM deliverables")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("SELECT id, name FROM projects")
        projects = {row["name"]: row["id"] for row in cursor.fetchall()}
        cursor.execute("SELECT id, name FROM team_members")
        members = {row["name"]: row["id"] for row in cursor.fetchall()}
        examples = (
            ("Customer Portal", "Discovery and requirements", "completed", 100, today - timedelta(days=20), "Ava Patel"),
            ("Customer Portal", "Design system and prototypes", "in_progress", 60, today + timedelta(days=4), "Noah Chen"),
            ("Customer Portal", "Customer dashboard", "in_progress", 35, today + timedelta(days=8), "Mia Member"),
            ("Mobile App", "App architecture", "in_progress", 40, today + timedelta(days=30), "Ava Patel"),
            ("Data Platform", "Data source inventory", "not_started", 0, today + timedelta(days=80), "Mia Member"),
        )
        deliverable_ids: dict[str, int] = {}
        for project, name, status, progress, due_date, assigned in examples:
            cursor.execute(
                """
                INSERT INTO deliverables
                    (project_id, name, status, progress, due_date, assigned_to)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (projects[project], name, status, progress, due_date, members[assigned]),
            )
            deliverable_ids[name] = cursor.fetchone()["id"]
        cursor.execute(
            "INSERT INTO deliverable_dependencies (deliverable_id, depends_on_id) VALUES (%s, %s)",
            (deliverable_ids["Customer dashboard"], deliverable_ids["Design system and prototypes"]),
        )

    cursor.execute("SELECT COUNT(*) AS count FROM allocations")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("SELECT id, name FROM projects")
        projects = {row["name"]: row["id"] for row in cursor.fetchall()}
        cursor.execute("SELECT id, name FROM team_members")
        members = {row["name"]: row["id"] for row in cursor.fetchall()}
        for member, project, allocation in (
            ("Mia Member", "Customer Portal", 65),
            ("Mia Member", "Mobile App", 50),
            ("Noah Chen", "Customer Portal", 70),
            ("Ava Patel", "Mobile App", 80),
        ):
            cursor.execute(
                """
                INSERT INTO allocations (member_id, project_id, allocation_percent)
                VALUES (%s, %s, %s)
                """,
                (members[member], projects[project], allocation),
            )

    cursor.execute("SELECT COUNT(*) AS count FROM budget_entries")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("SELECT id, name FROM projects")
        projects = {row["name"]: row["id"] for row in cursor.fetchall()}
        for project, category, entry_type, amount, description in (
            ("Customer Portal", "Engineering", "planned", 120000, "Project delivery plan"),
            ("Customer Portal", "Engineering", "spent", 46000, "Engineering and design"),
            ("Mobile App", "Product", "planned", 180000, "Project delivery plan"),
            ("Mobile App", "Product", "spent", 62000, "Discovery and implementation"),
            ("Data Platform", "Engineering", "planned", 95000, "Project delivery plan"),
        ):
            cursor.execute(
                """
                INSERT INTO budget_entries
                    (project_id, category, entry_type, amount, description)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (projects[project], category, entry_type, amount, description),
            )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Create application tables and seed empty tables with demo data."""
    del context
    try:
        method, _, _, _ = parse_request(event, "setup")
        if method != "GET":
            return response({"error": "Method not allowed"}, 405)
        with get_connection().cursor() as cursor:
            for statement in SCHEMA:
                cursor.execute(statement)
            _seed_samples(cursor)
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN
                    ('users', 'team_members', 'projects', 'deliverables',
                     'deliverable_dependencies', 'allocations', 'budget_entries')
                ORDER BY table_name
                """
            )
            tables = [row["table_name"] for row in cursor.fetchall()]
        return response({"status": "ok", "tables": tables})
    except Exception as error:
        return response({"error": str(error)}, 500)
