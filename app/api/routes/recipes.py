from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import get_engine
from app.models.control_plane_api_models import (
    RecipeCreateRequest,
    RecipeVersionCreateRequest,
)
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/api/v1", tags=["recipes"])


def get_recipe_service() -> RecipeService:
    return RecipeService(get_engine())


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/workspaces/{workspace_slug}/recipes")
def list_recipes(
    workspace_slug: str,
    service: RecipeService = Depends(get_recipe_service),
) -> dict:
    try:
        return service.list_recipes(workspace_slug)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: str, service: RecipeService = Depends(get_recipe_service)
) -> dict:
    recipe = service.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/recipes/{recipe_id}/versions")
def list_recipe_versions(
    recipe_id: str, service: RecipeService = Depends(get_recipe_service)
) -> dict:
    return service.list_recipe_versions(recipe_id)
