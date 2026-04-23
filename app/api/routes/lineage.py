from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.engine import Engine

from app.db.session import get_engine
from app.models.api import IngestionResponse
from app.repositories.lineage_events import LineageEventRepository
from app.services.event_resolver import parse_event
from app.services.ingestion import IngestionService
from app.services.lineage_query import LineageQueryService

router = APIRouter(prefix="/api/v1", tags=["lineage"])


def get_ingestion_service() -> IngestionService:
    return IngestionService(get_engine())


def get_lineage_query_service() -> LineageQueryService:
    return LineageQueryService(get_engine())


@router.post("/lineage", status_code=status.HTTP_201_CREATED)
async def create_lineage_event(
    request: Request,
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    payload = await request.json()
    try:
        event = parse_event(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors()
        ) from exc
    result = service.ingest(event, payload)
    return IngestionResponse(projected=result.projected)


@router.get("/lineage")
def get_lineage(
    nodeId: str = Query(...),
    depth: int = Query(default=1, ge=0, le=20),
    service: LineageQueryService = Depends(get_lineage_query_service),
):
    try:
        return service.get_lineage(node_id=nodeId, depth=depth)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/events/lineage")
def list_lineage_events(
    limit: int = Query(default=50, ge=1, le=200),
    engine: Engine = Depends(get_engine),
) -> dict:
    repo = LineageEventRepository()
    with engine.begin() as conn:
        events, total_count = repo.list_recent(conn, limit=limit)
        return {"events": events, "totalCount": total_count}
