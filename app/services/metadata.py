from __future__ import annotations

from sqlalchemy.engine import Engine

from app.repositories.metadata import MetadataRepository


class MetadataService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.repo = MetadataRepository()

    def list_namespaces(self) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_namespaces(conn).to_api_dict()

    def list_tags(self) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_tags(conn).to_api_dict()

    def upsert_tag(self, name: str, description: str) -> dict:
        with self.engine.begin() as conn:
            return self.repo.upsert_tag(conn, name, description).to_api_dict()

    def list_jobs(self, namespace: str | None, limit: int, offset: int, last_run_state: str | None = None) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_jobs(conn, namespace, limit, offset, last_run_state).to_api_dict()

    def get_job(self, namespace: str, name: str) -> dict | None:
        with self.engine.begin() as conn:
            job = self.repo.get_job_by_name(conn, namespace, name)
            return job.to_api_dict() if job else None

    def get_runs(self, namespace: str, name: str, limit: int, offset: int) -> dict:
        with self.engine.begin() as conn:
            return self.repo.get_runs_for_job(conn, namespace, name, limit, offset).to_api_dict()

    def list_datasets(self, namespace: str, limit: int, offset: int) -> dict:
        with self.engine.begin() as conn:
            return self.repo.list_datasets(conn, namespace, limit, offset).to_api_dict()

    def get_dataset(self, namespace: str, name: str) -> dict | None:
        with self.engine.begin() as conn:
            dataset = self.repo.get_dataset_by_name(conn, namespace, name)
            return dataset.to_api_dict() if dataset else None

    def get_dataset_versions(self, namespace: str, name: str, limit: int, offset: int) -> dict:
        with self.engine.begin() as conn:
            return self.repo.get_dataset_versions(conn, namespace, name, limit, offset).to_api_dict()

    def get_run_or_job_facets(self, run_id: str, facet_type: str) -> dict:
        with self.engine.begin() as conn:
            return self.repo.get_facets_for_run(conn, run_id, facet_type).to_api_dict()
