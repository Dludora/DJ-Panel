from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection

from app.db.schema import lineage_events
from app.models.openlineage import DatasetEvent, JobEvent, OpenLineageEvent, RunEvent


class StoredEventType(str, Enum):
    DATASET = 'DATASET'
    JOB = 'JOB'
    UNKNOWN = 'UNKNOWN'


class LineageEventRepository:
    def insert_raw_event(
        self, conn: Connection, event: OpenLineageEvent, payload: dict
    ) -> str:
        event_id = str(uuid4())
        if isinstance(event, RunEvent):
            event_type = event.event_type.value if event.event_type is not None else StoredEventType.UNKNOWN.value
        elif isinstance(event, DatasetEvent):
            event_type = StoredEventType.DATASET.value
        elif isinstance(event, JobEvent):
            event_type = StoredEventType.JOB.value
        else:
            event_type = StoredEventType.UNKNOWN.value

        conn.execute(
            insert(lineage_events).values(
                id=event_id,
                event_type=event_type,
                event_time=event.event_time or datetime.now(timezone.utc),
                job_namespace=event.job.namespace if isinstance(event, (RunEvent, JobEvent)) else None,
                job_name=event.job.name if isinstance(event, (RunEvent, JobEvent)) else None,
                run_id=event.run.run_id if isinstance(event, RunEvent) else None,
                producer=event.producer,
                payload=payload,
            )
        )
        return event_id

    def list_recent(self, conn: Connection, limit: int = 50) -> tuple[list[dict], int]:
        rows = (
            conn.execute(
                select(lineage_events)
                .order_by(lineage_events.c.created_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        total_count = conn.execute(
            select(func.count()).select_from(lineage_events)
        ).scalar_one()
        return [row['payload'] for row in rows], total_count
