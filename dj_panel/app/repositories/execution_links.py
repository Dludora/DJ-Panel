from __future__ import annotations

from sqlalchemy import insert, outerjoin, select, update
from sqlalchemy.engine import Connection

from dj_panel.app.db.schema import execution_links, runs
from dj_panel.app.db.rows import ExecutionLinkRow
from dj_panel.app.utils.common_utils import new_id, utc_now


class ExecutionLinkRepository:
    def upsert_execution_link(
        self,
        conn: Connection,
        *,
        run_submission_id: str | None,
        task_id: str | None,
        task_attempt_id: str | None,
        openlineage_run_id: str,
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
            "updated_at": now,
        }
        if existing:
            merged = {
                "run_submission_id": run_submission_id or existing.get("run_submission_id"),
                "task_id": task_id or existing.get("task_id"),
                "task_attempt_id": task_attempt_id or existing.get("task_attempt_id"),
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

    def get_by_attempt_id(
        self, conn: Connection, task_attempt_id: str
    ) -> ExecutionLinkRow | None:
        link_to_run = outerjoin(
            execution_links,
            runs,
            execution_links.c.openlineage_run_id == runs.c.run_id,
        )
        query = (
            select(
                execution_links,
                runs.c.id.label("lineage_run_id"),
                runs.c.job_id.label("lineage_job_id"),
            )
            .select_from(link_to_run)
            .where(execution_links.c.task_attempt_id == task_attempt_id)
        )
        row = conn.execute(query).mappings().first()
        return ExecutionLinkRow.from_mapping(row) if row else None
