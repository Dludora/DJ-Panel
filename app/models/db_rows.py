from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class NamespaceRow:
    name: str
    created_at: datetime
    updated_at: datetime
    owner_name: str
    description: str
    is_hidden: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> NamespaceRow:
        return cls(
            name=row['name'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            owner_name=row['owner_name'],
            description=row['description'],
            is_hidden=row['is_hidden'],
        )


@dataclass(frozen=True)
class JobRow:
    id: str
    namespace: str
    name: str
    location: str | None
    current_job_version_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> JobRow:
        return cls(
            id=row['id'],
            namespace=row['namespace'],
            name=row['name'],
            location=row['location'],
            current_job_version_id=row['current_job_version_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


@dataclass(frozen=True)
class RunRow:
    id: str
    run_id: str
    job_id: str
    event_time: datetime | None
    state: str | None
    started_at: datetime | None
    ended_at: datetime | None
    job_version_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> RunRow:
        return cls(
            id=row['id'],
            run_id=row['run_id'],
            job_id=row['job_id'],
            event_time=row['event_time'],
            state=row['state'],
            started_at=row['started_at'],
            ended_at=row['ended_at'],
            job_version_id=row['job_version_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


@dataclass(frozen=True)
class DatasetRow:
    id: str
    namespace: str
    name: str
    asset_kind: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> DatasetRow:
        return cls(
            id=row['id'],
            namespace=row['namespace'],
            name=row['name'],
            asset_kind=row.get('asset_kind', 'DATASET'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


@dataclass(frozen=True)
class DatasetVersionRow:
    id: str
    dataset_id: str
    version: str
    created_by_run_id: str | None
    storage_uri: str | None
    fields: list[dict[str, Any]]
    facets: dict[str, Any]
    lifecycle_state: str | None
    created_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> DatasetVersionRow:
        return cls(
            id=row['id'],
            dataset_id=row['dataset_id'],
            version=row['version'],
            created_by_run_id=row['created_by_run_id'],
            storage_uri=row.get('storage_uri'),
            fields=row['fields'],
            facets=row['facets'],
            lifecycle_state=row['lifecycle_state'],
            created_at=row['created_at'],
        )


@dataclass(frozen=True)
class JobVersionRow:
    id: str
    job_id: str
    version_hash: str
    is_current: bool
    created_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> JobVersionRow:
        return cls(
            id=row['id'],
            job_id=row['job_id'],
            version_hash=row['version_hash'],
            is_current=row['is_current'],
            created_at=row['created_at'],
        )
