from fastapi import FastAPI

from dj_panel.app.api.routes.assets import router as assets_router
from dj_panel.app.api.routes.lineage import router as lineage_router
from dj_panel.app.api.routes.recipes import router as recipes_router
from dj_panel.app.api.routes.run_submissions import router as run_submissions_router
from dj_panel.app.api.routes.tasks import router as tasks_router
from dj_panel.app.api.routes.workers import router as workers_router
from dj_panel.app.api.routes.workspaces import router as workspaces_router

app = FastAPI(title="DJ Panel Backend", version="0.1.0")
app.include_router(lineage_router)
app.include_router(assets_router)
app.include_router(workspaces_router)
app.include_router(recipes_router)
app.include_router(run_submissions_router)
app.include_router(workers_router)
app.include_router(tasks_router)
