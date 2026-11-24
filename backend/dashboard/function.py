"""Project portfolio dashboard Lambda handler."""

from typing import Any

from db import authorize_request, get_connection, parse_request, response


PROJECT_METRICS = """
    WITH deliverable_stats AS (
        SELECT project_id,
               COALESCE(AVG(progress), 0) AS progress,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE status = 'completed') AS completed,
               COUNT(*) FILTER (
                   WHERE due_date < CURRENT_DATE AND status <> 'completed'
               ) AS overdue
        FROM deliverables
        GROUP BY project_id
    )
    SELECT p.id, p.name, p.status, p.end_date,
           COALESCE(ds.progress, 0) AS deliverable_progress,
           COALESCE(ds.total, 0) AS deliverable_total,
           COALESCE(ds.completed, 0) AS deliverable_completed,
           COALESCE(ds.overdue, 0) AS overdue_deliverables
    FROM projects p
    LEFT JOIN deliverable_stats ds ON ds.project_id = p.id
"""


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return project status, risk, workload, budget, and dependency summaries."""
    del context
    try:
        method, _, _, _ = parse_request(event, "dashboard")
        if method == "OPTIONS":
            return response({}, 200)
        if method != "GET":
            return response({"error": "Method not allowed"}, 405)
        access_error = authorize_request(event, method)
        if access_error:
            return access_error

        with get_connection().cursor() as cursor:
            cursor.execute(
                """
                SELECT status, COUNT(*) AS project_count
                FROM projects GROUP BY status ORDER BY status
                """
            )
            status_overview = cursor.fetchall()

            cursor.execute(f"{PROJECT_METRICS} ORDER BY p.name")
            projects = cursor.fetchall()

            cursor.execute(
                f"""
                {PROJECT_METRICS}
                WHERE (
                    p.end_date <= CURRENT_DATE + INTERVAL '14 days'
                    AND COALESCE(ds.progress, 0) < 70
                ) OR COALESCE(ds.overdue, 0) > 0
                ORDER BY p.end_date NULLS LAST, p.name
                """
            )
            at_risk_projects = cursor.fetchall()

            cursor.execute(
                """
                SELECT tm.id, tm.name, tm.department,
                       SUM(a.allocation_percent) AS allocation_total
                FROM team_members tm
                JOIN allocations a ON a.member_id = tm.id
                GROUP BY tm.id
                HAVING SUM(a.allocation_percent) > 100
                ORDER BY allocation_total DESC, tm.name
                """
            )
            overallocated_members = cursor.fetchall()

            cursor.execute(
                """
                SELECT p.id AS project_id, p.name AS project_name,
                       COALESCE(SUM(b.amount) FILTER (WHERE b.entry_type = 'planned'), 0)
                           AS planned,
                       COALESCE(SUM(b.amount) FILTER (WHERE b.entry_type = 'spent'), 0)
                           AS spent
                FROM projects p
                LEFT JOIN budget_entries b ON b.project_id = p.id
                GROUP BY p.id
                ORDER BY p.name
                """
            )
            budgets = cursor.fetchall()

            cursor.execute(
                """
                SELECT d.id AS deliverable_id, d.name AS deliverable_name,
                       p.name AS project_name,
                       ARRAY(
                           SELECT parent.name
                           FROM deliverable_dependencies dependency
                           JOIN deliverables parent
                               ON parent.id = dependency.depends_on_id
                           WHERE dependency.deliverable_id = d.id
                           ORDER BY parent.name
                       ) AS depends_on
                FROM deliverables d
                JOIN projects p ON p.id = d.project_id
                ORDER BY p.name, d.due_date NULLS LAST, d.name
                """
            )
            dependency_chain = cursor.fetchall()

        return response({
            "status_overview": status_overview,
            "projects": projects,
            "at_risk_projects": at_risk_projects,
            "overallocated_members": overallocated_members,
            "budgets": budgets,
            "deliverable_completion": projects,
            "dependency_chain": dependency_chain,
        })
    except Exception as error:
        return response({"error": str(error)}, 500)
