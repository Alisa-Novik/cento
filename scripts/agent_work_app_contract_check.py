#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from agent_work_app import (
    add_local_attachment,
    add_local_journal,
    add_validation_evidence,
    create_local_issue,
    decide_review,
    init_db,
    issue_detail,
    issue_list,
    review_detail,
    review_queue,
    update_local_issue,
)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_empty_schema() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = Path(raw) / "agent-work.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            init_db(conn)
            tables = {
                row["name"]
                for row in conn.execute("select name from sqlite_master where type = 'table'")
            }
            payload = issue_list(conn)
    expected = {
        "projects",
        "trackers",
        "statuses",
        "users",
        "custom_fields",
        "custom_values",
        "issues",
        "journals",
        "journal_details",
        "attachments",
        "saved_queries",
        "migration_runs",
        "sync_meta",
    }
    missing = expected - tables
    assert_true(not missing, f"missing schema tables: {sorted(missing)}")
    assert_true(payload["issues"] == [], "empty database should list no issues")


def test_seeded_issue_detail() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = Path(raw) / "agent-work.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            init_db(conn)
            conn.execute(
                """
                insert into issues(id, subject, tracker, status, priority, assignee, updated_on, description, migrated_at)
                values (60, 'Agent Platform: Cento MCP server and Codex/Claude skills', 'Agent Task', 'Queued', 'Normal', 'Redmine Admin', '2026-04-30T01:16:00', 'Goals:\\n- Replace Redmine', '2026-04-30T01:16:00')
                """
            )
            conn.execute(
                "insert into journals(issue_id, created_on, notes, old_status, new_status) values (60, '2026-04-30T01:16:00', 'Status changed during fixture.', 'Review', 'Queued')"
            )
            conn.execute(
                "insert into attachments(issue_id, filename, size, path, created_on) values (60, 'validation-report.md', '15.2 KB', 'workspace/runs/agent-work/60/validation-report.md', '2026-04-30T01:16:00')"
            )
            conn.commit()
            listing = issue_list(conn)
            detail = issue_detail(conn, 60)
    assert_true(listing["total"] == 1, f"listing total: {listing['total']}")
    assert_true(detail["issue"]["id"] == 60, "detail issue id")
    assert_true(len(detail["journals"]) == 1, "journal fixture")
    assert_true(detail["attachments"][0]["filename"] == "validation-report.md", "attachment fixture")


def test_mutation_workflow() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = Path(raw) / "agent-work.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            init_db(conn)
            created = create_local_issue(
                conn,
                {
                    "subject": "Replacement workflow fixture",
                    "tracker": "Agent Task",
                    "status": "Queued",
                    "assignee": "alice",
                    "package": "redmine-replacement-v1",
                },
            )
            issue_id = created["issue"]["id"]
            updated = update_local_issue(conn, issue_id, {"status": "Running", "note": "Claimed by test."})
            add_local_journal(conn, issue_id, {"notes": "Validation note.", "author": "validator"})
            detail = add_local_attachment(
                conn,
                issue_id,
                {
                    "filename": "validation.md",
                    "size": "fixture",
                    "path": f"workspace/runs/agent-work/{issue_id}/validation.md",
                },
            )
    assert_true(updated["issue"]["status"] == "Running", "status update")
    assert_true(len(detail["journals"]) == 3, f"journal count: {len(detail['journals'])}")
    assert_true(detail["attachments"][0]["filename"] == "validation.md", "created attachment")


def test_review_queue_and_decision() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = Path(raw) / "agent-work.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            init_db(conn)
            created = create_local_issue(
                conn,
                {
                    "subject": "Review cockpit fixture",
                    "tracker": "Agent Task",
                    "status": "Review",
                    "assignee": "alice",
                    "package": "redmine-retirement",
                    "validation_report": "workspace/runs/agent-work/fixture/validation.md",
                },
            )
            issue_id = created["issue"]["id"]
            add_local_attachment(
                conn,
                issue_id,
                {
                    "filename": "review.png",
                    "size": "fixture",
                    "path": "workspace/runs/agent-work/fixture/review.png",
                    "evidence_type": "screenshot",
                },
            )
            add_validation_evidence(
                conn,
                issue_id,
                {
                    "label": "validator log",
                    "path": "workspace/runs/agent-work/fixture/codex.log",
                    "source": "validator",
                },
            )
            queue = review_queue(conn)
            detail = review_detail(conn, issue_id)
            decided = decide_review(conn, issue_id, {"decision": "approve", "note": "fixture approval"})
    assert_true(queue["total"] == 1, f"review queue total: {queue['total']}")
    assert_true(queue["items"][0]["confidence"] >= 80, "review confidence includes evidence")
    assert_true(any(item["kind"] == "screenshot" for item in detail["artifacts"]), "screenshot artifact")
    assert_true(any(item["kind"] == "logs" for item in detail["artifacts"]), "log artifact")
    assert_true(len(detail["attachments"]) == 1, f"attachment count: {len(detail['attachments'])}")
    assert_true(detail["attachments"][0]["filename"] == "review.png", "validation evidence should stay out of attachments")
    assert_true(len(detail["validation_evidences"]) == 1, f"validation evidence count: {len(detail['validation_evidences'])}")
    assert_true(detail["validation_evidences"][0]["label"] == "validator log", "validation evidence label")
    assert_true(decided["issue"]["status"] == "Done", "approve moves to done")
    assert_true(decided["issue"]["done_ratio"] == 100, "approve marks complete")
    decided_journal = next(item for item in decided["journals"] if item["notes"] == "fixture approval")
    assert_true(decided_journal["old_status"] == "Review", "approval journal old status")
    assert_true(decided_journal["new_status"] == "Done", "approval journal new status")


def main() -> int:
    test_empty_schema()
    test_seeded_issue_detail()
    test_mutation_workflow()
    test_review_queue_and_decision()
    print("agent work app contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
