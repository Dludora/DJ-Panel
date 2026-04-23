from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class NamespaceName(ApiModel):
    namespace: str
    name: str


class VersionedNamespaceName(NamespaceName):
    version: str


class NamespaceModel(ApiModel):
    name: str
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    owner_name: str = Field(alias='ownerName')
    description: str
    is_hidden: bool = Field(alias='isHidden')


class FieldModel(ApiModel):
    name: str
    type: str | None = None
    tags: list[Any] = Field(default_factory=list)
    description: str = ''


class TagModel(ApiModel):
    name: str
    description: str


class JobVersionName(ApiModel):
    name: str
    namespace: str
    version: str


class RunModel(ApiModel):
    id: str
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    nominal_start_time: datetime | None = Field(alias='nominalStartTime')
    nominal_end_time: datetime | None = Field(alias='nominalEndTime')
    state: str
    job_version: JobVersionName = Field(alias='jobVersion')
    started_at: datetime | None = Field(alias='startedAt')
    ended_at: datetime | None = Field(alias='endedAt')
    duration_ms: int = Field(alias='durationMs')
    args: dict[str, Any] = Field(default_factory=dict)
    facets: dict[str, Any] = Field(default_factory=dict)


class JobModel(ApiModel):
    id: NamespaceName
    type: str
    name: str
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    inputs: list[NamespaceName] = Field(default_factory=list)
    outputs: list[NamespaceName] = Field(default_factory=list)
    namespace: str
    location: str
    description: str
    simple_name: str = Field(alias='simpleName')
    latest_run: RunModel | None = Field(alias='latestRun')
    latest_runs: list[RunModel] = Field(default_factory=list, alias='latestRuns')
    tags: list[Any] = Field(default_factory=list)
    parent_job_name: str | None = Field(default=None, alias='parentJobName')
    parent_job_uuid: str | None = Field(default=None, alias='parentJobUuid')


class DatasetModel(ApiModel):
    id: NamespaceName
    type: str
    name: str
    physical_name: str = Field(alias='physicalName')
    created_at: datetime = Field(alias='createdAt')
    updated_at: datetime = Field(alias='updatedAt')
    namespace: str
    source_name: str = Field(alias='sourceName')
    fields: list[FieldModel] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    last_modified_at: datetime = Field(alias='lastModifiedAt')
    description: str
    facets: dict[str, Any] = Field(default_factory=dict)
    deleted: bool
    column_lineage: Any | None = Field(default=None, alias='columnLineage')


class DatasetVersionModel(ApiModel):
    id: VersionedNamespaceName
    type: str
    created_by_run: RunModel | None = Field(alias='createdByRun')
    name: str
    physical_name: str = Field(alias='physicalName')
    created_at: datetime = Field(alias='createdAt')
    version: str
    namespace: str
    source_name: str = Field(alias='sourceName')
    fields: list[FieldModel] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    last_modified_at: datetime = Field(alias='lastModifiedAt')
    description: str
    lifecycle_state: str = Field(alias='lifecycleState')
    facets: dict[str, Any] = Field(default_factory=dict)


class RunFacetsModel(ApiModel):
    run_id: str = Field(alias='runId')
    facets: dict[str, Any] = Field(default_factory=dict)


class TagsResponse(ApiModel):
    tags: list[TagModel] = Field(default_factory=list)


class NamespacesResponse(ApiModel):
    namespaces: list[NamespaceModel] = Field(default_factory=list)


class JobsResponse(ApiModel):
    jobs: list[JobModel] = Field(default_factory=list)
    total_count: int = Field(alias='totalCount')


class RunsResponse(ApiModel):
    runs: list[RunModel] = Field(default_factory=list)
    total_count: int = Field(alias='totalCount')


class DatasetsResponse(ApiModel):
    datasets: list[DatasetModel] = Field(default_factory=list)
    total_count: int = Field(alias='totalCount')


class DatasetVersionsResponse(ApiModel):
    versions: list[DatasetVersionModel] = Field(default_factory=list)
    total_count: int = Field(alias='totalCount')
