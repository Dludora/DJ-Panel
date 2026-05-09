from __future__ import annotations

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import execution_links
from app.db.rows import ExecutionLinkRow
from app.utils.common_utils import new_id, utc_now


class ExecutionLinkRepository:
    def upsert_execution_link(
        self,
        conn: Connection,
        *,
        run_submission_id: str | None,
        task_id: str | None,
        task_attempt_id: str | None,
        openlineage_run_id: str,
        lineage_run_id: str | None = None,
        lineage_job_id: str | None = None,
    ) -> ExecutionLinkRow:
        existing = conn.execute(
            select(execution_links).where(
                execution_links.c.openlineage_run_id == openlineage_run_id
            )
        ).mappings().first()
        now = utc_now()
        values = {
            "run_submission_id": run_submission_id,
            "task_id": task_id,
            "task_attempt_id": task_attempt_id,
            "lineage_run_id": lineage_run_id,
            "lineage_job_id": lineage_job_id,
            "updated_at": now,
        }
        if existing:
            merged = {
                "run_submission_id": run_submission_id or existing.get("run_submission_id"),
                "task_id": task_id or existing.get("task_id"),
                "task_attempt_id": task_attempt_id or existing.get("task_attempt_id"),
                "lineage_run_id": lineage_run_id or existing.get("lineage_run_id"),
                "lineage_job_id": lineage_job_id or existing.get("lineage_job_id"),
                "updated_at": now,
            }
            conn.execute(
                update(execution_links)
                .where(execution_links.c.id == existing["id"])
                .values(**merged)
            )
            return ExecutionLinkRow.from_mapping({**dict(existing), **merged})

        row = {
            "id": new_id(),
            "openlineage_run_id": openlineage_run_id,
            "created_at": now,
            **values,
        }
        conn.execute(insert(execution_links).values(**row))
        return ExecutionLinkRow.from_mapping(row)

    def attach_projected_run(
        self,
        conn: Connection,
        *,
        openlineage_run_id: str,
        lineage_run_id: str,
        lineage_job_id: str | None,
    ) -> ExecutionLinkRow | None:
        existing = conn.execute(
            select(execution_links).where(
                execution_links.c.openlineage_run_id == openlineage_run_id
            )
        ).mappings().first()
        if not existing:
            return None
        values = {
            "lineage_run_id": lineage_run_id,
            "lineage_job_id": lineage_job_id,
            "updated_at": utc_now(),
        }
        conn.execute(
            update(execution_links)
            .where(execution_links.c.id == existing["id"])
            .values(**values)
        )
        return ExecutionLinkRow.from_mapping({**dict(existing), **values})

    def get_by_attempt_id(
        self, conn: Connection, task_attempt_id: str
    ) -> ExecutionLinkRow | None:
        row = conn.execute(
            select(execution_links).where(execution_links.c.task_attempt_id == task_attempt_id)
        ).mappings().first()
        return ExecutionLinkRow.from_mapping(row) if row else None
