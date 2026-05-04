from __future__ import annotations

from typing import Optional

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import workspace_members, workspaces
from app.db.rows import WorkspaceMemberRow, WorkspaceRow
from app.repositories.utils import new_id, utc_now


class WorkspaceRepository:
    def create_workspace(self, conn: Connection, slug: str, name: str, description: str) -> WorkspaceRow:
        now = utc_now()
        workspace_id = new_id()
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

    def upsert_member(
        self,
        conn: Connection,
        workspace_id: str,
        user_name: str,
        role: str,
    ) -> WorkspaceMemberRow:
        existing = conn.execute(
            select(workspace_members).where(
                workspace_members.c.workspace_id == workspace_id,
                workspace_members.c.user_name == user_name,
            )
        ).mappings().first()
        if existing:
            conn.execute(
                update(workspace_members)
                .where(workspace_members.c.id == existing["id"])
                .values(role=role)
            )
            return WorkspaceMemberRow.from_mapping({**dict(existing), "role": role})

        now = utc_now()
        member_id = new_id()
        conn.execute(
            insert(workspace_members).values(
                id=member_id,
                workspace_id=workspace_id,
                user_name=user_name,
                role=role,
                created_at=now,
            )
        )
        return WorkspaceMemberRow(
            id=member_id,
            workspace_id=workspace_id,
            user_name=user_name,
            role=role,
            created_at=now,
        )

    def list_members(self, conn: Connection, workspace_id: str) -> list[WorkspaceMemberRow]:
        rows = conn.execute(
            select(workspace_members)
            .where(workspace_members.c.workspace_id == workspace_id)
            .order_by(workspace_members.c.role.asc(), workspace_members.c.user_name.asc())
        ).mappings().all()
        return [WorkspaceMemberRow.from_mapping(row) for row in rows]
