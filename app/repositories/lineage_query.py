from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.db.schema import job_version_io_mapping, job_versions
from app.models.types.lineage import JobVersionIOType


class LineageQueryRepository:
    def get_current_job_inputs_outputs(self, conn: Connection, job_version_id: str) -> tuple[list[str], list[str]]:
        rows = conn.execute(
            select(job_version_io_mapping.c.asset_id, job_version_io_mapping.c.io_type).where(
                job_version_io_mapping.c.job_version_id == job_version_id
            )
        ).mappings().all()
        inputs = [row['asset_id'] for row in rows if row['io_type'] == JobVersionIOType.INPUT.value]
        outputs = [row['asset_id'] for row in rows if row['io_type'] == JobVersionIOType.OUTPUT.value]
        return inputs, outputs

    def get_current_job_version_id(self, conn: Connection, job_id: str) -> str | None:
        row = conn.execute(
            select(job_versions.c.id).where(job_versions.c.job_id == job_id, job_versions.c.is_current.is_(True))
        ).first()
        return row[0] if row else None

    def get_current_jobs_for_dataset(self, conn: Connection, dataset_id: str) -> tuple[list[str], list[str]]:
        rows = conn.execute(
            select(job_versions.c.job_id, job_version_io_mapping.c.io_type)
            .select_from(job_versions.join(job_version_io_mapping, job_versions.c.id == job_version_io_mapping.c.job_version_id))
            .where(job_versions.c.is_current.is_(True), job_version_io_mapping.c.asset_id == dataset_id)
        ).mappings().all()
        consumers = [row['job_id'] for row in rows if row['io_type'] == JobVersionIOType.INPUT.value]
        producers = [row['job_id'] for row in rows if row['io_type'] == JobVersionIOType.OUTPUT.value]
        return producers, consumers
