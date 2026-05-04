from __future__ import annotations

from app.db.engine import get_engine
from app.services.ingestion import IngestionService
from app.services.lineage_query import LineageQueryService
from app.services.metadata import MetadataService
from app.services.recipes import RecipeService
from app.services.run_submissions import RunSubmissionService
from app.services.tasks import TaskService
from app.services.workers import WorkerService
from app.services.workspaces import WorkspaceService


def get_ingestion_service() -> IngestionService:
    return IngestionService(get_engine())


def get_lineage_query_service() -> LineageQueryService:
    return LineageQueryService(get_engine())


def get_metadata_service() -> MetadataService:
    return MetadataService(get_engine())


def get_recipe_service() -> RecipeService:
    return RecipeService(get_engine())


def get_run_submission_service() -> RunSubmissionService:
    return RunSubmissionService(get_engine())


def get_task_service() -> TaskService:
    return TaskService(get_engine())


def get_worker_service() -> WorkerService:
    return WorkerService(get_engine())


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(get_engine())
