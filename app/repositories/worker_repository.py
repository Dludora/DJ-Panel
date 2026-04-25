from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import worker_heartbeats, workers
from app.models.db_models import WorkerRow
from app.models.shared_enums import WorkerStatus


class WorkerRepository:
    def register_worker(
        self,
        conn: Connection,
        workspace_id: str,
        worker_id: str,
        display_name: str,
        labels: dict,
        capabilities: dict,
        max_concurrency: int,
    ) -> WorkerRow:
        now = datetime.now(timezone.utc)
        existing = self.get_worker_by_id(conn, worker_id)
        if existing:
            conn.execute(
                update(workers)
                .where(workers.c.id == worker_id)
                .values(
                    workspace_id=workspace_id,
                    display_name=display_name,
                    labels=labels,
                    capabilities=capabilities,
                    max_concurrency=max_concurrency,
                    status=WorkerStatus.ACTIVE.value,
                    last_heartbeat_at=now,
                    updated_at=now,
                )
            )
        else:
            conn.execute(
                insert(workers).values(
                    id=worker_id,
                    workspace_id=workspace_id,
                    display_name=display_name,
                    status=WorkerStatus.ACTIVE.value,
                    labels=labels,
                    capabilities=capabilities,
                    max_concurrency=max_concurrency,
                    last_heartbeat_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        self.record_heartbeat(conn, worker_id, WorkerStatus.ACTIVE.value, labels, capabilities, heartbeat_at=now)
        return self.get_worker_by_id(conn, worker_id)

    def record_heartbeat(
        self,
        conn: Connection,
        worker_id: str,
        status: str,
        labels: dict,
        capabilities: dict,
        *,
        heartbeat_at: Optional[datetime] = None,
    ) -> WorkerRow:
        heartbeat_at = heartbeat_at or datetime.now(timezone.utc)
        conn.execute(
            insert(worker_heartbeats).values(
                id=str(uuid4()),
                worker_id=worker_id,
                status=status,
                labels=labels,
                capabilities=capabilities,
                heartbeat_at=heartbeat_at,
            )
        )
        conn.execute(
            update(workers)
            .where(workers.c.id == worker_id)
            .values(
                status=status,
                labels=labels,
                capabilities=capabilities,
                last_heartbeat_at=heartbeat_at,
                updated_at=heartbeat_at,
            )
        )
        return self.get_worker_by_id(conn, worker_id)

    def list_workers(self, conn: Connection, workspace_id: str) -> list[WorkerRow]:
        rows = conn.execute(
            select(workers).where(workers.c.workspace_id == workspace_id).order_by(workers.c.updated_at.desc())
        ).mappings().all()
        return [WorkerRow.from_mapping(row) for row in rows]

    def get_worker_by_id(self, conn: Connection, worker_id: str) -> Optional[WorkerRow]:
        row = conn.execute(select(workers).where(workers.c.id == worker_id)).mappings().first()
        return WorkerRow.from_mapping(row) if row else None
