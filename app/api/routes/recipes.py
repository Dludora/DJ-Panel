from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_recipe_service
from app.api.errors import not_found
from app.models.api import (
    RecipeCreateRequest,
    RecipeVersionCreateRequest,
)
from app.services.recipes import RecipeService

router = APIRouter(prefix="/api/v1", tags=["recipes"])


@router.post(
    "/workspaces/{workspace_slug}/recipes", status_code=status.HTTP_201_CREATED
)
def create_recipe(
    workspace_slug: str,
    payload: RecipeCreateRequest,
    service: RecipeService = Depends(get_recipe_service),
) -> dict:
    try:
        return service.create_recipe(workspace_slug, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/workspaces/{workspace_slug}/recipes")
def list_recipes(
    workspace_slug: str,
    service: RecipeService = Depends(get_recipe_service),
) -> dict:
    try:
        return service.list_recipes(workspace_slug)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: str, service: RecipeService = Depends(get_recipe_service)
) -> dict:
    recipe = service.get_recipe(recipe_id)
    if not recipe:
        raise not_found("recipe not found")
    return recipe


@router.post("/recipes/{recipe_id}/versions", status_code=status.HTTP_201_CREATED)
def create_recipe_version(
    recipe_id: str,
    payload: RecipeVersionCreateRequest,
    service: RecipeService = Depends(get_recipe_service),
) -> dict:
    try:
        return service.create_recipe_version(recipe_id, payload)
    except ValueError as exc:
        raise not_found(str(exc)) from exc


@router.get("/recipes/{recipe_id}/versions")
def list_recipe_versions(
    recipe_id: str, service: RecipeService = Depends(get_recipe_service)
) -> dict:
    return service.list_recipe_versions(recipe_id)
