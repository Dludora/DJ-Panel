from __future__ import annotations

from sqlalchemy.engine import Engine
from typing import Optional

from app.models.control_plane_api_models import (
    RecipeResponse,
    RecipesResponse,
    RecipeVersionResponse,
    RecipeVersionsResponse,
)
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.workspace_repository import WorkspaceRepository


class RecipeService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.recipe_repo = RecipeRepository()
        self.workspace_repo = WorkspaceRepository()

    def create_recipe(self, workspace_slug: str, payload) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            recipe = self.recipe_repo.create_recipe(
                conn,
                workspace_id=workspace.id,
                name=payload.name,
                description=payload.description,
                owner_name=payload.owner_name,
            )
            version = self.recipe_repo.create_recipe_version(
                conn,
                recipe_id=recipe.id,
                created_by=payload.owner_name,
                recipe_body=payload.recipe_body,
                command=payload.command,
                script_path=payload.script_path,
                parameter_schema=payload.parameter_schema,
                env_template=payload.env_template,
                execution_spec=payload.execution_spec,
                timeout_seconds=payload.timeout_seconds,
                lineage_namespace=payload.lineage_namespace,
                lineage_job_name=payload.lineage_job_name,
            )
            refreshed = self.recipe_repo.get_recipe_by_id(conn, recipe.id)
            return self._recipe_response(refreshed, version).to_api_dict()

    def create_recipe_version(self, recipe_id: str, payload) -> dict:
        with self.engine.begin() as conn:
            version = self.recipe_repo.create_recipe_version(
                conn,
                recipe_id=recipe_id,
                created_by=payload.created_by,
                recipe_body=payload.recipe_body,
                command=payload.command,
                script_path=payload.script_path,
                parameter_schema=payload.parameter_schema,
                env_template=payload.env_template,
                execution_spec=payload.execution_spec,
                timeout_seconds=payload.timeout_seconds,
                lineage_namespace=payload.lineage_namespace,
                lineage_job_name=payload.lineage_job_name,
            )
            return self._version_response(version).to_api_dict()

    def list_recipes(self, workspace_slug: str) -> dict:
        with self.engine.begin() as conn:
            workspace = self.workspace_repo.get_by_slug(conn, workspace_slug)
            if not workspace:
                raise ValueError('workspace not found')
            recipes = self.recipe_repo.list_recipes(conn, workspace.id)
            items = []
            for recipe in recipes:
                current = self.recipe_repo.get_recipe_version_by_id(conn, recipe.current_version_id) if recipe.current_version_id else None
                items.append(self._recipe_response(recipe, current))
            return RecipesResponse(recipes=items).to_api_dict()

    def get_recipe(self, recipe_id: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            recipe = self.recipe_repo.get_recipe_by_id(conn, recipe_id)
            if not recipe:
                return None
            current = self.recipe_repo.get_recipe_version_by_id(conn, recipe.current_version_id) if recipe.current_version_id else None
            return self._recipe_response(recipe, current).to_api_dict()

    def list_recipe_versions(self, recipe_id: str) -> dict:
        with self.engine.begin() as conn:
            versions = self.recipe_repo.list_recipe_versions(conn, recipe_id)
            return RecipeVersionsResponse(versions=[self._version_response(v) for v in versions]).to_api_dict()

    def _recipe_response(self, recipe, current_version) -> RecipeResponse:
        return RecipeResponse(
            id=recipe.id,
            workspaceId=recipe.workspace_id,
            name=recipe.name,
            description=recipe.description,
            ownerName=recipe.owner_name,
            currentVersionId=recipe.current_version_id,
            createdAt=recipe.created_at,
            updatedAt=recipe.updated_at,
            currentVersion=self._version_response(current_version) if current_version else None,
        )

    @staticmethod
    def _version_response(version) -> RecipeVersionResponse:
        return RecipeVersionResponse(
            id=version.id,
            recipeId=version.recipe_id,
            versionNumber=version.version_number,
            recipeBody=version.recipe_body,
            command=version.command,
            scriptPath=version.script_path,
            parameterSchema=version.parameter_schema,
            envTemplate=version.env_template,
            executionSpec=version.execution_spec,
            timeoutSeconds=version.timeout_seconds,
            lineageNamespace=version.lineage_namespace,
            lineageJobName=version.lineage_job_name,
            createdBy=version.created_by,
            createdAt=version.created_at,
        )
