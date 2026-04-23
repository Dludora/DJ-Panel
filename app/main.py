from fastapi import FastAPI

from app.api.routes.lineage import router as lineage_router
from app.api.routes.metadata import router as metadata_router

app = FastAPI(title="DJ Panel Backend", version="0.1.0")
app.include_router(lineage_router)
app.include_router(metadata_router)
