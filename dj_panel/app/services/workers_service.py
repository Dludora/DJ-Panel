from __future__ import annotations

from sqlalchemy.engine import Engine

from dj_panel.app.models.api import WorkerResponse, WorkersResponse
from dj_panel.app.repositories.workers_repo import WorkerRepository
from dj_panel.app.repositories.workspaces_repo import WorkspaceRepository


class WorkerService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.workspace_repo = WorkspaceRepository()
        self.worker_repo = WorkerRepository()

    def register_worker(self, workspace_slug: str, payload) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError("workspace not found")
            worker = self.worker_repo.register_worker(
                conn,
                workspace_id=workspace.id,
                worker_id=payload.worker_id,
                display_name=payload.display_name,
                labels=payload.labels,
                capabilities=payload.capabilities,
                max_concurrency=payload.max_concurrency,
            )
            return self._response(worker).to_api_dict()

    def heartbeat(self, worker_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            worker = self.worker_repo.get_worker_by_id(conn, worker_id)
            if not worker:
                raise ValueError("worker not found")
            updated = self.worker_repo.record_heartbeat(
                conn,
                worker_id=worker_id,
                status=payload.status or worker.status,
                labels=payload.labels or worker.labels,
                capabilities=payload.capabilities or worker.capabilities,
            )
            return self._response(updated).to_api_dict()

    def list_workers(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError("workspace not found")
            workers = self.worker_repo.list_workers(conn, workspace.id)
            return WorkersResponse(
                workers=[self._response(worker) for worker in workers]
            ).to_api_dict()

    @staticmethod
    def _response(worker) -> WorkerResponse:
        return WorkerResponse(
            id=worker.id,
            workspaceId=worker.workspace_id,
            displayName=worker.display_name,
            status=worker.status,
            labels=worker.labels,
            capabilities=worker.capabilities,
            maxConcurrency=worker.max_concurrency,
            lastHeartbeatAt=worker.last_heartbeat_at,
            createdAt=worker.created_at,
            updatedAt=worker.updated_at,
        )
