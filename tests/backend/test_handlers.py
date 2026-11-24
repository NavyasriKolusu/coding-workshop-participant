"""Unit tests for Lambda handlers with mocked PostgreSQL connections."""

import base64
import importlib.util
import json
import sys
import types
from collections import deque
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND / "setup"))
import db as shared_db  # noqa: E402


def load_handler(service):
    """Load a service handler while sharing the common db module."""
    spec = importlib.util.spec_from_file_location(
        f"acme_{service}", BACKEND / service / "function.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


health = load_handler("health")
setup = load_handler("setup")
projects = load_handler("projects")
team_members = load_handler("team_members")
allocations = load_handler("allocations")
deliverables = load_handler("deliverables")
budget_entries = load_handler("budget_entries")
auth = load_handler("auth")
dashboard = load_handler("dashboard")


class FakeCursor:
    """Small cursor fake with queued fetch results."""

    def __init__(self, one=None, many=None, ones=None, manys=None):
        self.one = one
        self.many = many if many is not None else []
        self.ones = deque(ones or [])
        self.manys = deque(manys or [])
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return self.ones.popleft() if self.ones else self.one

    def fetchall(self):
        return self.manys.popleft() if self.manys else self.many


class FakeConnection:
    """Connection fake returning a scripted cursor."""

    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.closed = 0

    def cursor(self):
        return self.fake_cursor


def make_event(service, method="GET", path=None, body=None, query=None, headers=None):
    """Build a payload-v2 Lambda event for a service handler."""
    raw_path = path if path is not None else f"/api/{service}"
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": raw_path,
        "body": json.dumps(body) if body is not None else None,
        "queryStringParameters": query or {},
        "headers": headers or {},
    }


def result(response):
    """Return a decoded Lambda body."""
    return json.loads(response["body"]) if response["body"] else None


def patch_connection(monkeypatch, module, cursor):
    """Replace a handler's connection factory with a fake cursor."""
    monkeypatch.setattr(module, "get_connection", lambda: FakeConnection(cursor))


def allow_access(monkeypatch, module):
    """Allow a test request through the handler role guard."""
    monkeypatch.setattr(module, "authorize_request", lambda event, method: None)


def test_health_returns_ok():
    response = health.handler({}, None)
    assert response["statusCode"] == 200
    assert result(response) == {"status": "ok"}


def test_shared_response_and_request_helpers():
    response = shared_db.response({"amount": Decimal("12.5"), "date": date(2026, 1, 2)})
    assert result(response) == {"amount": 12.5, "date": "2026-01-02"}
    assert shared_db.json_default(datetime(2026, 1, 2, 3, 4)) == "2026-01-02T03:04:00"
    with pytest.raises(TypeError):
        shared_db.json_default(object())

    local_event = make_event("projects", method="GET", path="/5", query={"status": "active"})
    assert shared_db.parse_request(local_event, "projects") == (
        "GET", "/5", {}, {"status": "active"}
    )
    aws_event = make_event(
        "projects",
        method="POST",
        path="/api/projects",
        body={"name": "Portal"},
    )
    assert shared_db.parse_request(aws_event, "projects") == (
        "POST", "/", {"name": "Portal"}, {}
    )
    encoded = base64.b64encode(b'{"name":"Encoded"}').decode()
    aws_event["body"] = encoded
    aws_event["isBase64Encoded"] = True
    assert shared_db.parse_request(aws_event, "projects")[2] == {"name": "Encoded"}
    aws_event["body"] = "[]"
    aws_event["isBase64Encoded"] = False
    with pytest.raises(ValueError, match="JSON object"):
        shared_db.parse_request(aws_event, "projects")


def test_database_connection_is_reused(monkeypatch):
    calls = []
    connection = FakeConnection(FakeCursor())
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.__path__ = []
    fake_psycopg.connect = lambda **kwargs: calls.append(kwargs) or connection
    fake_rows = types.ModuleType("psycopg.rows")
    fake_rows.dict_row = object()
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", fake_rows)
    monkeypatch.setattr(shared_db, "_connection", None)
    monkeypatch.setenv("POSTGRES_HOST", "db.example")

    assert shared_db.get_connection() is connection
    assert shared_db.get_connection() is connection
    assert len(calls) == 1
    assert calls[0]["host"] == "db.example"
    assert calls[0]["autocommit"] is True
    assert calls[0]["row_factory"] is fake_rows.dict_row

    connection.closed = 1
    replacement = FakeConnection(FakeCursor())
    fake_psycopg.connect = lambda **kwargs: calls.append(kwargs) or replacement
    assert shared_db.get_connection() is replacement
    assert len(calls) == 2
    monkeypatch.setattr(shared_db, "_connection", None)


def test_signed_token_and_authorization_helpers(monkeypatch):
    user = {"username": "member", "role": "member"}
    token = shared_db.issue_token(user)
    assert shared_db._decode_token(token)["username"] == "member"
    with pytest.raises(PermissionError, match="Invalid"):
        shared_db._decode_token(f"{token}x")

    monkeypatch.setattr(shared_db, "current_user", lambda event: user)
    assert shared_db.require_user({}, {"member"}) is None
    assert shared_db.require_user({}, {"admin"})["statusCode"] == 403
    monkeypatch.setattr(
        shared_db, "current_user", Mock(side_effect=PermissionError("Authentication required"))
    )
    assert shared_db.require_user({}, {"member"})["statusCode"] == 401
    monkeypatch.setattr(shared_db, "require_user", Mock(return_value=None))
    shared_db.authorize_request({}, "GET")
    assert shared_db.require_user.call_args.args[1] == {"admin", "manager", "member"}
    shared_db.authorize_request({}, "POST")
    assert shared_db.require_user.call_args.args[1] == {"admin", "manager"}


def test_current_user_reads_header_and_local_proxy_fallback(monkeypatch):
    member = {"id": 3, "username": "member", "role": "member", "name": "Mia"}
    monkeypatch.setattr(shared_db, "_decode_token", lambda token: {"username": "member"})
    patch_connection(monkeypatch, shared_db, FakeCursor(one=member))
    assert shared_db.current_user({"headers": {"Authorization": "Bearer signed"}}) == member

    monkeypatch.setenv("IS_LOCAL", "true")
    event = {"headers": {"content-type": "application/json; acme-token=signed"}}
    assert shared_db.current_user(event) == member
    with pytest.raises(PermissionError, match="Authentication required"):
        shared_db.current_user({"headers": {}})


def test_setup_seeds_each_empty_table():
    class SeedCursor(FakeCursor):
        def __init__(self):
            super().__init__()
            self.next_id = 1

        def execute(self, statement, params=None):
            super().execute(statement, params)
            normalized = " ".join(statement.split())
            if normalized.startswith("SELECT COUNT(*)"):
                self.one = {"count": 0}
            elif normalized == "SELECT id, name FROM projects":
                self.many = [
                    {"id": 1, "name": "Customer Portal"},
                    {"id": 2, "name": "Mobile App"},
                    {"id": 3, "name": "Data Platform"},
                ]
            elif normalized == "SELECT id, name FROM team_members":
                self.many = [
                    {"id": 1, "name": "Mia Member"},
                    {"id": 2, "name": "Noah Chen"},
                    {"id": 3, "name": "Ava Patel"},
                ]
            elif "INSERT INTO deliverables" in normalized and "RETURNING id" in normalized:
                self.one = {"id": self.next_id}
                self.next_id += 1

    cursor = SeedCursor()
    setup._seed_samples(cursor)
    statements = [query for query, _ in cursor.statements]
    assert sum("INSERT INTO users" in query for query in statements) == 3
    assert sum("INSERT INTO team_members" in query for query in statements) == 3
    assert sum("INSERT INTO projects" in query for query in statements) == 3
    assert sum("INSERT INTO deliverables" in query for query in statements) == 5
    assert sum("INSERT INTO allocations" in query for query in statements) == 4
    assert sum("INSERT INTO budget_entries" in query for query in statements) == 5
    assert any("INSERT INTO deliverable_dependencies" in query for query in statements)


def test_setup_handler_returns_tables(monkeypatch):
    assert setup.handler(make_event("setup", "POST"), None)["statusCode"] == 405
    cursor = FakeCursor(many=[{"table_name": "projects"}, {"table_name": "users"}])
    patch_connection(monkeypatch, setup, cursor)
    monkeypatch.setattr(setup, "_seed_samples", lambda cursor: None)
    response = setup.handler(make_event("setup"), None)
    assert response["statusCode"] == 200
    assert result(response)["tables"] == ["projects", "users"]


@pytest.mark.parametrize(
    "body,expected_status",
    [
        ({"name": "Portal"}, 201),
        ({"name": "Portal", "status": "bad"}, 400),
        ({}, 400),
    ],
)
def test_projects_create_and_validate(monkeypatch, body, expected_status):
    cursor = FakeCursor(one={"id": 1, "name": "Portal"})
    patch_connection(monkeypatch, projects, cursor)
    allow_access(monkeypatch, projects)
    response = projects.handler(make_event("projects", "POST", body=body), None)
    assert response["statusCode"] == expected_status


def test_projects_read_update_delete_and_errors(monkeypatch):
    allow_access(monkeypatch, projects)
    project = {"id": 1, "name": "Portal", "status": "active"}
    cursor = FakeCursor(many=[project], one=project)
    patch_connection(monkeypatch, projects, cursor)
    assert result(projects.handler(make_event("projects", query={"status": "active"}), None)) == [project]
    assert result(projects.handler(make_event("projects", path="/api/projects/1"), None)) == project
    patch_connection(monkeypatch, projects, FakeCursor(one=None))
    assert projects.handler(make_event("projects", "GET", path="/api/projects/999"), None)["statusCode"] == 404

    cursor = FakeCursor(one=project)
    patch_connection(monkeypatch, projects, cursor)
    assert projects.handler(make_event("projects", "PUT", "/api/projects/1", {"name": "Portal"}), None)["statusCode"] == 200
    cursor = FakeCursor(one={"id": 1})
    patch_connection(monkeypatch, projects, cursor)
    assert projects.handler(make_event("projects", "DELETE", "/api/projects/1"), None)["statusCode"] == 200
    assert projects.handler(make_event("projects", "PATCH"), None)["statusCode"] == 405

    monkeypatch.setattr(projects, "get_connection", Mock(side_effect=RuntimeError("db down")))
    assert projects.handler(make_event("projects"), None)["statusCode"] == 500
    monkeypatch.setattr(projects, "authorize_request", lambda event, method: {"statusCode": 401, "body": "{}"})
    assert projects.handler(make_event("projects"), None)["statusCode"] == 401


def test_team_members_crud_and_validation(monkeypatch):
    allow_access(monkeypatch, team_members)
    member = {"id": 2, "name": "Noah", "email": "noah@example.com", "allocation_total": 70}
    cursor = FakeCursor(many=[member], one=member)
    patch_connection(monkeypatch, team_members, cursor)
    assert result(team_members.handler(make_event("team_members", query={"department": "Design"}), None)) == [member]
    assert team_members.handler(make_event("team_members", "GET", "/api/team_members/2"), None)["statusCode"] == 200

    cursor = FakeCursor(ones=[{"id": 2}, member])
    patch_connection(monkeypatch, team_members, cursor)
    assert team_members.handler(
        make_event("team_members", "POST", body={"name": "Noah", "email": "noah@example.com", "department": "Design"}),
        None,
    )["statusCode"] == 201
    cursor = FakeCursor(ones=[{"id": 2}, member])
    patch_connection(monkeypatch, team_members, cursor)
    assert team_members.handler(
        make_event("team_members", "PUT", "/api/team_members/2", {"title": "Designer"}),
        None,
    )["statusCode"] == 200
    cursor = FakeCursor(one={"id": 2})
    patch_connection(monkeypatch, team_members, cursor)
    assert team_members.handler(make_event("team_members", "DELETE", "/api/team_members/2"), None)["statusCode"] == 200
    assert team_members.handler(
        make_event("team_members", "POST", body={"name": "X", "email": "bad", "department": "Design"}),
        None,
    )["statusCode"] == 400
    assert team_members.handler(make_event("team_members", "GET", "/api/team_members/nope"), None)["statusCode"] == 400


def test_allocations_crud_and_bounds(monkeypatch):
    allow_access(monkeypatch, allocations)
    item = {"id": 7, "member_id": 2, "allocation_percent": 60, "member_allocation_total": 110}
    cursor = FakeCursor(many=[item], one=item)
    patch_connection(monkeypatch, allocations, cursor)
    assert result(allocations.handler(make_event("allocations", query={"department": "Design"}), None)) == [item]
    assert allocations.handler(make_event("allocations", "GET", "/api/allocations/7"), None)["statusCode"] == 200

    cursor = FakeCursor(ones=[{"id": 7}, item])
    patch_connection(monkeypatch, allocations, cursor)
    assert allocations.handler(
        make_event("allocations", "POST", body={"member_id": 2, "project_id": 1, "allocation_percent": 60}),
        None,
    )["statusCode"] == 201
    cursor = FakeCursor(ones=[{"id": 7}, item])
    patch_connection(monkeypatch, allocations, cursor)
    assert allocations.handler(
        make_event("allocations", "PUT", "/api/allocations/7", {"allocation_percent": 60}),
        None,
    )["statusCode"] == 200
    cursor = FakeCursor(one={"id": 7})
    patch_connection(monkeypatch, allocations, cursor)
    assert allocations.handler(make_event("allocations", "DELETE", "/api/allocations/7"), None)["statusCode"] == 200
    assert allocations.handler(
        make_event("allocations", "POST", body={"member_id": 2, "project_id": 1, "allocation_percent": 101}),
        None,
    )["statusCode"] == 400
    assert allocations.handler(make_event("allocations", "GET", "/api/allocations/nope"), None)["statusCode"] == 400


def test_deliverables_crud_and_dependency_cycles(monkeypatch):
    allow_access(monkeypatch, deliverables)
    item = {"id": 4, "name": "Build API", "depends_on_ids": [], "dependency_names": []}
    cursor = FakeCursor(many=[item], one=item)
    patch_connection(monkeypatch, deliverables, cursor)
    assert result(deliverables.handler(make_event("deliverables", query={"status": "in_progress"}), None)) == [item]
    assert deliverables.handler(make_event("deliverables", "GET", "/api/deliverables/4"), None)["statusCode"] == 200

    cursor = FakeCursor(ones=[{"id": 8}, item])
    patch_connection(monkeypatch, deliverables, cursor)
    assert deliverables.handler(
        make_event("deliverables", "POST", body={"project_id": 1, "name": "Build API"}),
        None,
    )["statusCode"] == 201
    cursor = FakeCursor(ones=[{"id": 4}, item])
    patch_connection(monkeypatch, deliverables, cursor)
    assert deliverables.handler(
        make_event("deliverables", "PUT", "/api/deliverables/4", {"progress": 80}),
        None,
    )["statusCode"] == 200

    cursor = FakeCursor(manys=[[{"id": 5}], [{"deliverable_id": 5, "depends_on_id": 4}]])
    with pytest.raises(ValueError, match="cycle"):
        deliverables._validate_dependencies(cursor, [5], 4)
    cursor = FakeCursor(many=[])
    with pytest.raises(ValueError, match="do not exist"):
        deliverables._validate_dependencies(cursor, [99])
    with pytest.raises(ValueError, match="itself"):
        deliverables._validate_dependencies(FakeCursor(), [4], 4)
    with pytest.raises(ValueError, match="unique"):
        deliverables._validate({"depends_on": [2, 2]})
    assert deliverables.handler(
        make_event("deliverables", "POST", body={"project_id": 1, "name": "Bad", "depends_on": "2"}),
        None,
    )["statusCode"] == 400

    cursor = FakeCursor(one={"id": 4})
    patch_connection(monkeypatch, deliverables, cursor)
    assert deliverables.handler(make_event("deliverables", "DELETE", "/api/deliverables/4"), None)["statusCode"] == 200


def test_budget_entries_crud_and_validation(monkeypatch):
    allow_access(monkeypatch, budget_entries)
    entry = {"id": 5, "project_id": 1, "amount": Decimal("300.00"), "entry_type": "spent"}
    cursor = FakeCursor(many=[entry], one=entry)
    patch_connection(monkeypatch, budget_entries, cursor)
    assert budget_entries.handler(
        make_event(
            "budget_entries",
            query={"search": "cloud", "status": "spent", "department": "Engineering"},
        ),
        None,
    )["statusCode"] == 200
    assert budget_entries.handler(make_event("budget_entries", "GET", "/api/budget_entries/5"), None)["statusCode"] == 200

    body = {"project_id": 1, "category": "Cloud", "entry_type": "planned", "amount": 300}
    cursor = FakeCursor(ones=[{"id": 6}, entry])
    patch_connection(monkeypatch, budget_entries, cursor)
    assert budget_entries.handler(make_event("budget_entries", "POST", body=body), None)["statusCode"] == 201
    cursor = FakeCursor(ones=[{"id": 5}, entry])
    patch_connection(monkeypatch, budget_entries, cursor)
    assert budget_entries.handler(
        make_event("budget_entries", "PUT", "/api/budget_entries/5", {"amount": 350}),
        None,
    )["statusCode"] == 200
    cursor = FakeCursor(one={"id": 5})
    patch_connection(monkeypatch, budget_entries, cursor)
    assert budget_entries.handler(make_event("budget_entries", "DELETE", "/api/budget_entries/5"), None)["statusCode"] == 200
    for bad_amount in (-1, float("inf"), "not-money"):
        assert budget_entries.handler(
            make_event("budget_entries", "POST", body={**body, "amount": bad_amount}),
            None,
        )["statusCode"] == 400
    assert budget_entries.handler(
        make_event("budget_entries", "GET", "/api/budget_entries/missing"),
        None,
    )["statusCode"] == 400
    with pytest.raises(ValueError, match="integer"):
        budget_entries._entry_id("/nope")
    for invalid in (
        ({}, True),
        ({"category": " "}, False),
        ({"entry_type": "unknown"}, False),
        ({"project_id": 0}, False),
        ({"project_id": "bad"}, False),
        ({"amount": "bad"}, False),
        ({}, False),
        ({"unexpected": "field"}, False),
    ):
        with pytest.raises(ValueError):
            budget_entries._validate(invalid[0], invalid[1])

    patch_connection(monkeypatch, budget_entries, FakeCursor(one=None))
    assert budget_entries.handler(
        make_event("budget_entries", "GET", "/api/budget_entries/999"),
        None,
    )["statusCode"] == 404
    patch_connection(monkeypatch, budget_entries, FakeCursor(one=None))
    assert budget_entries.handler(
        make_event("budget_entries", "PUT", "/api/budget_entries/999", {"amount": 1}),
        None,
    )["statusCode"] == 404
    patch_connection(monkeypatch, budget_entries, FakeCursor(one=None))
    assert budget_entries.handler(
        make_event("budget_entries", "DELETE", "/api/budget_entries/999"),
        None,
    )["statusCode"] == 404
    assert budget_entries.handler(make_event("budget_entries", "PATCH"), None)["statusCode"] == 405


def test_auth_login_users_and_role_denial(monkeypatch):
    stored_hash = auth._hash_password("password123")
    assert auth._verify_password("password123", stored_hash)
    assert not auth._verify_password("wrong", stored_hash)
    assert not auth._verify_password("password", "bad-hash")

    user = {
        "id": 1, "username": "admin", "name": "Admin", "role": "admin",
        "created_at": date(2026, 1, 1), "password_hash": stored_hash,
    }
    patch_connection(monkeypatch, auth, FakeCursor(one=user))
    login = auth.handler(
        make_event("auth", "POST", "/api/auth/login", {"username": "admin", "password": "password123"}),
        None,
    )
    assert login["statusCode"] == 200
    assert "token" in result(login)

    patch_connection(monkeypatch, auth, FakeCursor(one=None))
    assert auth.handler(
        make_event("auth", "POST", "/api/auth/login", {"username": "admin", "password": "wrong"}),
        None,
    )["statusCode"] == 401
    assert auth.handler(make_event("auth", "POST", "/api/auth/login", {}), None)["statusCode"] == 400

    monkeypatch.setattr(auth, "current_user", lambda event: {"id": 1, "username": "admin"})
    assert auth.handler(make_event("auth", "GET", "/api/auth/me"), None)["statusCode"] == 200
    monkeypatch.setattr(auth, "current_user", Mock(side_effect=PermissionError("Authentication required")))
    assert auth.handler(make_event("auth", "GET", "/api/auth/me"), None)["statusCode"] == 401

    monkeypatch.setattr(auth, "require_user", lambda event, roles: None)
    cursor = FakeCursor(many=[{"id": 1, "username": "admin", "role": "admin"}])
    patch_connection(monkeypatch, auth, cursor)
    assert auth.handler(
        make_event("auth", "GET", "/api/auth/users", query={"search": "admin", "status": "admin"}),
        None,
    )["statusCode"] == 200
    cursor = FakeCursor(one={"id": 2, "username": "new", "role": "member"})
    patch_connection(monkeypatch, auth, cursor)
    assert auth.handler(
        make_event("auth", "POST", "/api/auth/users", {
            "username": "new", "name": "New Member", "role": "member", "password": "password123",
        }),
        None,
    )["statusCode"] == 201
    cursor = FakeCursor(one={"id": 2, "username": "new", "role": "manager"})
    patch_connection(monkeypatch, auth, cursor)
    assert auth.handler(
        make_event("auth", "PUT", "/api/auth/users/2", {"role": "manager"}),
        None,
    )["statusCode"] == 200
    monkeypatch.setattr(auth, "current_user", lambda event: {"id": 1})
    assert auth.handler(make_event("auth", "DELETE", "/api/auth/users/1"), None)["statusCode"] == 400
    cursor = FakeCursor(one={"id": 2})
    patch_connection(monkeypatch, auth, cursor)
    assert auth.handler(make_event("auth", "DELETE", "/api/auth/users/2"), None)["statusCode"] == 200
    with pytest.raises(ValueError, match="integer"):
        auth._user_id("/users/not-a-number")
    with pytest.raises(ValueError, match="Unknown"):
        auth._user_id("/other")
    for invalid in (
        ({}, True),
        ({"username": "new", "name": "New", "password": "password123", "role": "unknown"}, True),
        ({"name": " "}, False),
        ({"username": " "}, False),
        ({"role": "unknown"}, False),
        ({"password": "short"}, False),
        ({}, False),
        ({"extra": "value"}, False),
    ):
        with pytest.raises(ValueError):
            auth._validate_user(invalid[0], invalid[1])
    monkeypatch.setattr(auth, "require_user", lambda event, roles: {"statusCode": 403, "body": "{}"})
    assert auth.handler(make_event("auth", "GET", "/api/auth/users"), None)["statusCode"] == 403
    assert auth.handler(make_event("auth", "GET", "/api/auth/unknown"), None)["statusCode"] == 404


def test_deliverables_validation_and_dependency_update(monkeypatch):
    with pytest.raises(ValueError, match="integer"):
        deliverables._deliverable_id("/not-an-id")
    for invalid in (
        ({}, True),
        ({"name": " "}, False),
        ({"status": "unknown"}, False),
        ({"progress": 101}, False),
        ({}, False),
        ({"unexpected": "field"}, False),
        ({"depends_on": "2"}, False),
        ({"depends_on": [0]}, False),
    ):
        with pytest.raises(ValueError):
            deliverables._validate(invalid[0], invalid[1])

    allow_access(monkeypatch, deliverables)
    item = {"id": 1, "name": "API", "depends_on_ids": [2], "dependency_names": ["Design"]}
    cursor = FakeCursor(
        ones=[item, item],
        manys=[[{"id": 2}], []],
    )
    patch_connection(monkeypatch, deliverables, cursor)
    assert deliverables.handler(
        make_event("deliverables", "PUT", "/api/deliverables/1", {"depends_on": [2]}),
        None,
    )["statusCode"] == 200
    assert any("DELETE FROM deliverable_dependencies" in statement for statement, _ in cursor.statements)

    patch_connection(monkeypatch, deliverables, FakeCursor(one=None))
    assert deliverables.handler(
        make_event("deliverables", "GET", "/api/deliverables/999"),
        None,
    )["statusCode"] == 404
    patch_connection(monkeypatch, deliverables, FakeCursor(one=None))
    assert deliverables.handler(
        make_event("deliverables", "DELETE", "/api/deliverables/999"),
        None,
    )["statusCode"] == 404
    assert deliverables.handler(make_event("deliverables", "PATCH"), None)["statusCode"] == 405


def test_dashboard_aggregates_and_authorizes(monkeypatch):
    allow_access(monkeypatch, dashboard)
    responses = [
        [{"status": "active", "project_count": 1}],
        [{"id": 1, "name": "Portal"}],
        [{"id": 1, "name": "Portal"}],
        [{"id": 2, "name": "Mia", "allocation_total": 110}],
        [{"project_name": "Portal", "planned": Decimal("100"), "spent": Decimal("40")}],
        [{"deliverable_name": "API", "depends_on": ["Design"]}],
    ]
    patch_connection(monkeypatch, dashboard, FakeCursor(manys=responses))
    response = dashboard.handler(make_event("dashboard"), None)
    assert response["statusCode"] == 200
    data = result(response)
    assert len(data["at_risk_projects"]) == 1
    assert data["overallocated_members"][0]["allocation_total"] == 110
    assert data["budgets"][0]["spent"] == 40.0
    assert dashboard.handler(make_event("dashboard", "POST"), None)["statusCode"] == 405
    monkeypatch.setattr(dashboard, "authorize_request", lambda event, method: {"statusCode": 401, "body": "{}"})
    assert dashboard.handler(make_event("dashboard"), None)["statusCode"] == 401
    allow_access(monkeypatch, dashboard)
    monkeypatch.setattr(dashboard, "get_connection", Mock(side_effect=RuntimeError("db down")))
    assert dashboard.handler(make_event("dashboard"), None)["statusCode"] == 500
