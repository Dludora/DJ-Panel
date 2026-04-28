from __future__ import annotations

from sqlalchemy.engine import Engine

from app.models.api.control_plane import (
    WorkspaceMemberResponse,
    WorkspaceMembersResponse,
    WorkspaceResponse,
    WorkspacesResponse,
)
from app.repositories.workspaces import WorkspaceRepository


class WorkspaceService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.repo = WorkspaceRepository()

    def create_workspace(self, slug: str, name: str, description: str, owner_name: str | None = None) -> dict:
        with self.engine.begin() as conn:
            row = self.repo.create_workspace(conn, slug, name, description)
            if owner_name:
                self.repo.upsert_member(conn, row.id, owner_name, "OWNER")
            return self._workspace_response(row).to_api_dict()

    def list_workspaces(self) -> dict:
        with self.engine.begin() as conn:
            rows = self.repo.list_workspaces(conn)
            return WorkspacesResponse(
                workspaces=[self._workspace_response(row) for row in rows]
            ).to_api_dict()

    def add_member(self, workspace_slug: str, user_name: str, role: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            member = self.repo.upsert_member(conn, workspace.id, user_name, role)
            return self._member_response(member).to_api_dict()

    def list_members(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            members = self.repo.list_members(conn, workspace.id)
            return WorkspaceMembersResponse(
                members=[self._member_response(member) for member in members]
            ).to_api_dict()

    @staticmethod
    def _workspace_response(row) -> WorkspaceResponse:
        return WorkspaceResponse(
            id=row.id,
            slug=row.slug,
            name=row.name,
            description=row.description,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    @staticmethod
    def _member_response(member) -> WorkspaceMemberResponse:
        return WorkspaceMemberResponse(
            id=member.id,
            workspaceId=member.workspace_id,
            userName=member.user_name,
            role=member.role,
            createdAt=member.created_at,
        )
