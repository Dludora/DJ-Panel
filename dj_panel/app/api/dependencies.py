from __future__ import annotations

from dj_panel.app.db.engine import get_engine
from dj_panel.app.services.assets_service import AssetService
from dj_panel.app.services.lineage_service import LineageService
from dj_panel.app.services.recipes_service import RecipeService
from dj_panel.app.services.run_submissions_service import RunSubmissionService
from dj_panel.app.services.tasks_service import TaskService
from dj_panel.app.services.workers_service import WorkerService
from dj_panel.app.services.workspaces_service import WorkspaceService


def get_lineage_service() -> LineageService:
    return LineageService(get_engine())


def get_asset_service() -> AssetService:
    return AssetService(get_engine())


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
