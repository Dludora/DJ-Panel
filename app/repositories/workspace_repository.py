from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import workspaces
from app.models.db_models import WorkspaceRow


class WorkspaceRepository:
    def create_workspace(self, conn: Connection, slug: str, name: str, description: str) -> WorkspaceRow:
        now = datetime.now(timezone.utc)
        workspace_id = str(uuid4())
        conn.execute(
            insert(workspaces).values(
                id=workspace_id,
                slug=slug,
                name=name,
                description=description,
                created_at=now,
                updated_at=now,
            )
        )
        return self.get_by_id(conn, workspace_id)

    def list_workspaces(self, conn: Connection) -> list[WorkspaceRow]:
        rows = conn.execute(select(workspaces).order_by(workspaces.c.name.asc())).mappings().all()
        return [WorkspaceRow.from_mapping(row) for row in rows]

    def get_by_slug(self, conn: Connection, slug: str) -> Optional[WorkspaceRow]:
        row = conn.execute(select(workspaces).where(workspaces.c.slug == slug)).mappings().first()
        return WorkspaceRow.from_mapping(row) if row else None

    def get_by_id(self, conn: Connection, workspace_id: str) -> WorkspaceRow:
        row = conn.execute(select(workspaces).where(workspaces.c.id == workspace_id)).mappings().one()
        return WorkspaceRow.from_mapping(row)
