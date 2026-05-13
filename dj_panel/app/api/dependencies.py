from __future__ import annotations

from dj_panel.app.db.engine import get_engine
from dj_panel.app.services.assets import AssetService
from dj_panel.app.services.lineage import LineageService
from dj_panel.app.services.recipes import RecipeService
from dj_panel.app.services.run_submissions import RunSubmissionService
from dj_panel.app.services.tasks import TaskService
from dj_panel.app.services.workers import WorkerService
from dj_panel.app.services.workspaces import WorkspaceService


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
