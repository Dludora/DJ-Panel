from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import run_submissions
from app.db.rows.control_plane import RunSubmissionRow
from app.models.types.control_plane import RunSubmissionStatus
from app.repositories.utils import new_id, utc_now


class RunSubmissionRepository:
    def create_run_submission(
        self,
        conn: Connection,
        workspace_id: str,
        recipe_id: str | None,
        recipe_version_id: str | None,
        name: str | None,
        requested_by: str,
        submission_kind: str,
        parameters: dict,
        spec: dict,
    ) -> RunSubmissionRow:
        run_id = new_id()
        now = utc_now()
        conn.execute(
            insert(run_submissions).values(
                id=run_id,
                workspace_id=workspace_id,
                recipe_id=recipe_id,
                recipe_version_id=recipe_version_id,
                name=name,
                requested_by=requested_by,
                submission_kind=submission_kind,
                status=RunSubmissionStatus.PENDING.value,
                parameters=parameters,
                spec=spec,
                created_at=now,
            )
        )
        return self.get_run_submission_by_id(conn, run_id)

    def list_run_submissions(
        self, conn: Connection, workspace_id: str
    ) -> list[RunSubmissionRow]:
        rows = (
            conn.execute(
                select(run_submissions)
                .where(run_submissions.c.workspace_id == workspace_id)
                .order_by(run_submissions.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        return [RunSubmissionRow.from_mapping(row) for row in rows]

    def get_run_submission_by_id(
        self, conn: Connection, run_id: str
    ) -> Optional[RunSubmissionRow]:
        row = (
            conn.execute(select(run_submissions).where(run_submissions.c.id == run_id))
            .mappings()
            .first()
        )
        return RunSubmissionRow.from_mapping(row) if row else None

    def update_run_submission_status(
        self,
        conn: Connection,
        run_id: str,
        status: str,
        *,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        failure_reason: Optional[str] = None,
        root_lineage_node_id: Optional[str] = None,
    ) -> RunSubmissionRow:
        values: dict[str, object] = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if ended_at is not None:
            values["ended_at"] = ended_at
        if failure_reason is not None:
            values["failure_reason"] = failure_reason
        if root_lineage_node_id is not None:
            values["root_lineage_node_id"] = root_lineage_node_id
        conn.execute(
            update(run_submissions).where(run_submissions.c.id == run_id).values(**values)
        )
        return self.get_run_submission_by_id(conn, run_id)
