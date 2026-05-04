from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.engine import Engine

from app.api.dependencies import get_ingestion_service, get_lineage_query_service
from app.api.errors import bad_request, validation_error
from app.db.engine import get_engine
from app.models.api import IngestionResponse
from app.repositories.lineage_events import LineageEventRepository
from app.services.event_resolver import parse_event
from app.services.ingestion import IngestionService
from app.services.lineage_query import LineageQueryService

router = APIRouter(prefix="/api/v1", tags=["lineage"])


@router.post("/lineage", status_code=status.HTTP_201_CREATED)
async def create_lineage_event(
    request: Request,
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    payload = await request.json()
    try:
        event = parse_event(payload)
    except ValidationError as exc:
        raise validation_error(exc.errors()) from exc
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
        raise bad_request(str(exc)) from exc


@router.get("/events/lineage")
def list_lineage_events(
    limit: int = Query(default=50, ge=1, le=200),
    engine: Engine = Depends(get_engine),
) -> dict:
    repo = LineageEventRepository()
    with engine.begin() as conn:
        events, total_count = repo.list_recent(conn, limit=limit)
        return {"events": events, "totalCount": total_count}
