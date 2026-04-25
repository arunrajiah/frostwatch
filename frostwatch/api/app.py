from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from frostwatch.api.limiter import limiter
from frostwatch.api.routes.anomalies import router as anomalies_router
from frostwatch.api.routes.dashboard import router as dashboard_router
from frostwatch.api.routes.queries import router as queries_router
from frostwatch.api.routes.reports import router as reports_router
from frostwatch.api.routes.scheduler_routes import router as scheduler_router
from frostwatch.api.routes.settings import router as settings_router
from frostwatch.api.routes.sync import router as sync_router
from frostwatch.api.routes.warehouses import router as warehouses_router
from frostwatch.core.config import load_config
from frostwatch.core.db import init_db
from frostwatch.core.scheduler import create_scheduler
from frostwatch.llm.factory import get_llm_provider


class AppState:
    def __init__(self):
        self.config = None
        self.scheduler = None
        self.llm_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = AppState()

    config = load_config()
    state.config = config

    await init_db(config.db_path)

    try:
        state.llm_provider = get_llm_provider(config)
    except Exception:
        state.llm_provider = None

    scheduler = create_scheduler(config, state)
    state.scheduler = scheduler
    scheduler.start()

    app.state.config = state.config
    app.state.scheduler = state.scheduler
    app.state.llm_provider = state.llm_provider

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="FrostWatch",
        description="AI-powered cost and query observability for Snowflake",
        version="0.1.5",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    cors_origins = load_config().cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api"
    app.include_router(dashboard_router, prefix=api_prefix, tags=["dashboard"])
    app.include_router(queries_router, prefix=api_prefix, tags=["queries"])
    app.include_router(warehouses_router, prefix=api_prefix, tags=["warehouses"])
    app.include_router(anomalies_router, prefix=api_prefix, tags=["anomalies"])
    app.include_router(reports_router, prefix=api_prefix, tags=["reports"])
    app.include_router(settings_router, prefix=api_prefix, tags=["settings"])
    app.include_router(sync_router, prefix=api_prefix, tags=["sync"])
    app.include_router(scheduler_router, prefix=api_prefix, tags=["scheduler"])

    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

    if frontend_dist.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dist / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str, request: Request):
            index = frontend_dist / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"detail": "Frontend not built. Run: cd frontend && npm run build"}

    return app


app = create_app()
