from __future__ import annotations

from typing import Optional

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.db.schema import recipe_versions, recipes
from app.db.rows import RecipeRow, RecipeVersionRow
from app.repositories.utils import new_id, utc_now


class RecipeRepository:
    def create_recipe(
        self,
        conn: Connection,
        workspace_id: str,
        name: str,
        description: str,
        owner_name: str,
    ) -> RecipeRow:
        recipe_id = new_id()
        now = utc_now()
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
    ) -> RecipeVersionRow:
        latest_version = conn.execute(
            select(recipe_versions.c.version_number)
            .where(recipe_versions.c.recipe_id == recipe_id)
            .order_by(recipe_versions.c.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        version_number = (latest_version or 0) + 1
        version_id = new_id()
        now = utc_now()
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
