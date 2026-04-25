from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import recipe_runs
from app.models.db_models import RecipeRunRow
from app.models.shared_enums import RecipeRunStatus


class RecipeRunRepository:
    def create_recipe_run(
        self,
        conn: Connection,
        workspace_id: str,
        recipe_id: str,
        recipe_version_id: str,
        requested_by: str,
        parameters: dict,
    ) -> RecipeRunRow:
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        conn.execute(
            insert(recipe_runs).values(
                id=run_id,
                workspace_id=workspace_id,
                recipe_id=recipe_id,
                recipe_version_id=recipe_version_id,
                requested_by=requested_by,
                status=RecipeRunStatus.PENDING.value,
                parameters=parameters,
                created_at=now,
            )
        )
        return self.get_recipe_run_by_id(conn, run_id)

    def list_recipe_runs(self, conn: Connection, workspace_id: str) -> list[RecipeRunRow]:
        rows = conn.execute(
            select(recipe_runs)
            .where(recipe_runs.c.workspace_id == workspace_id)
            .order_by(recipe_runs.c.created_at.desc())
        ).mappings().all()
        return [RecipeRunRow.from_mapping(row) for row in rows]

    def get_recipe_run_by_id(self, conn: Connection, run_id: str) -> Optional[RecipeRunRow]:
        row = conn.execute(select(recipe_runs).where(recipe_runs.c.id == run_id)).mappings().first()
        return RecipeRunRow.from_mapping(row) if row else None

    def update_recipe_run_status(
        self,
        conn: Connection,
        run_id: str,
        status: str,
        *,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        failure_reason: Optional[str] = None,
        root_lineage_node_id: Optional[str] = None,
    ) -> RecipeRunRow:
        values: dict[str, object] = {'status': status}
        if started_at is not None:
            values['started_at'] = started_at
        if ended_at is not None:
            values['ended_at'] = ended_at
        if failure_reason is not None:
            values['failure_reason'] = failure_reason
        if root_lineage_node_id is not None:
            values['root_lineage_node_id'] = root_lineage_node_id
        conn.execute(update(recipe_runs).where(recipe_runs.c.id == run_id).values(**values))
        return self.get_recipe_run_by_id(conn, run_id)
