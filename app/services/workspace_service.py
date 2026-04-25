from __future__ import annotations

from sqlalchemy.engine import Engine

from app.models.control_plane_api_models import WorkspaceResponse, WorkspacesResponse
from app.repositories.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.repo = WorkspaceRepository()

    def create_workspace(self, slug: str, name: str, description: str) -> dict:
        with self.engine.begin() as conn:
            row = self.repo.create_workspace(conn, slug, name, description)
            return WorkspaceResponse(
                id=row.id,
                slug=row.slug,
                name=row.name,
                description=row.description,
                createdAt=row.created_at,
                updatedAt=row.updated_at,
            ).to_api_dict()

    def list_workspaces(self) -> dict:
        with self.engine.begin() as conn:
            rows = self.repo.list_workspaces(conn)
            return WorkspacesResponse(
                workspaces=[
                    WorkspaceResponse(
                        id=row.id,
                        slug=row.slug,
                        name=row.name,
                        description=row.description,
                        createdAt=row.created_at,
                        updatedAt=row.updated_at,
                    )
                    for row in rows
                ]
            ).to_api_dict()
