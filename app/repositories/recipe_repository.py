from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import recipe_versions, recipes
from app.models.db_models import RecipeRow, RecipeVersionRow


class RecipeRepository:
    def create_recipe(
        self,
        conn: Connection,
        workspace_id: str,
        name: str,
        description: str,
        owner_name: str,
    ) -> RecipeRow:
        recipe_id = str(uuid4())
        now = datetime.now(timezone.utc)
        conn.execute(
            insert(recipes).values(
                id=recipe_id,
                workspace_id=workspace_id,
                name=name,
                description=description,
                owner_name=owner_name,
                created_at=now,
                updated_at=now,
            )
        )
        return self.get_recipe_by_id(conn, recipe_id)

    def list_recipes(self, conn: Connection, workspace_id: str) -> list[RecipeRow]:
        rows = conn.execute(
            select(recipes).where(recipes.c.workspace_id == workspace_id).order_by(recipes.c.updated_at.desc())
        ).mappings().all()
        return [RecipeRow.from_mapping(row) for row in rows]

    def get_recipe_by_id(self, conn: Connection, recipe_id: str) -> Optional[RecipeRow]:
        row = conn.execute(select(recipes).where(recipes.c.id == recipe_id)).mappings().first()
        return RecipeRow.from_mapping(row) if row else None

    def get_recipe_by_name(self, conn: Connection, workspace_id: str, recipe_name: str) -> Optional[RecipeRow]:
        row = conn.execute(
            select(recipes).where(recipes.c.workspace_id == workspace_id, recipes.c.name == recipe_name)
        ).mappings().first()
        return RecipeRow.from_mapping(row) if row else None

    def create_recipe_version(
        self,
        conn: Connection,
        recipe_id: str,
        created_by: str,
        recipe_body: dict,
        command: str,
        script_path: str,
        parameter_schema: dict,
        env_template: dict,
        execution_spec: dict,
        timeout_seconds: int,
        lineage_namespace: Optional[str],
        lineage_job_name: Optional[str],
    ) -> RecipeVersionRow:
        latest_version = conn.execute(
            select(recipe_versions.c.version_number)
            .where(recipe_versions.c.recipe_id == recipe_id)
            .order_by(recipe_versions.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        version_number = (latest_version or 0) + 1
        version_id = str(uuid4())
        now = datetime.now(timezone.utc)
        conn.execute(
            insert(recipe_versions).values(
                id=version_id,
                recipe_id=recipe_id,
                version_number=version_number,
                recipe_body=recipe_body,
                command=command,
                script_path=script_path,
                parameter_schema=parameter_schema,
                env_template=env_template,
                execution_spec=execution_spec,
                timeout_seconds=timeout_seconds,
                lineage_namespace=lineage_namespace,
                lineage_job_name=lineage_job_name,
                created_by=created_by,
                created_at=now,
            )
        )
        conn.execute(
            update(recipes)
            .where(recipes.c.id == recipe_id)
            .values(current_version_id=version_id, updated_at=now)
        )
        return self.get_recipe_version_by_id(conn, version_id)

    def list_recipe_versions(self, conn: Connection, recipe_id: str) -> list[RecipeVersionRow]:
        rows = conn.execute(
            select(recipe_versions)
            .where(recipe_versions.c.recipe_id == recipe_id)
            .order_by(recipe_versions.c.version_number.desc())
        ).mappings().all()
        return [RecipeVersionRow.from_mapping(row) for row in rows]

    def get_recipe_version_by_id(self, conn: Connection, version_id: str) -> Optional[RecipeVersionRow]:
        row = conn.execute(select(recipe_versions).where(recipe_versions.c.id == version_id)).mappings().first()
        return RecipeVersionRow.from_mapping(row) if row else None
