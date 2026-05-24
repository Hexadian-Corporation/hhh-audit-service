import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psutil
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from hexadian_auth_common.fastapi import JWTAuthDependency, override_jwt_auth, register_exception_handlers
from hhh_events import EventSubscriber
from motor.motor_asyncio import AsyncIOMotorClient
from opyoid import Injector

from src.application.ports.inbound.audit_service import AuditService
from src.application.ports.outbound.audit_repository import AuditRepository
from src.infrastructure.adapters.inbound.api.audit_router import init_router, router
from src.infrastructure.adapters.inbound.events.audit_event_handler import AuditEventHandler
from src.infrastructure.config.dependencies import AppModule
from src.infrastructure.config.settings import Settings

_PROC = psutil.Process()
_PROC.cpu_percent()  # establish baseline
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    )
    module = AppModule(settings)
    injector = Injector([module])
    service: AuditService = injector.inject(AuditService)
    repository: AuditRepository = injector.inject(AuditRepository)
    jwt_auth = injector.inject(JWTAuthDependency)
    motor_client = injector.inject(AsyncIOMotorClient)
    subscriber = injector.inject(EventSubscriber)
    handler = injector.inject(AuditEventHandler)
    init_router(service)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: ensure the time-series collection + TTL are in place before subscriber starts.
        # No try/except – failure must propagate.
        await repository.ensure_timeseries_collection()

        # Spawn the events subscriber as a background task.
        task = asyncio.create_task(subscriber.run(handler, label="audit-service"))
        app.state.subscriber_task = task
        app.state.subscriber_alive = True

        def _subscriber_done(t: asyncio.Task) -> None:
            if t.cancelled():
                app.state.subscriber_alive = False
                logger.info("audit subscriber cancelled (shutdown)")
            else:
                exc = t.exception()
                if exc is not None:
                    app.state.subscriber_alive = False
                    logger.error("audit subscriber task crashed", exc_info=exc)

        task.add_done_callback(_subscriber_done)
        logger.info("hhh-audit-service started: subscriber=%s", settings.subscriber_id)

        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            try:
                motor_client.close()
            except Exception:
                logger.exception("motor_client.close failed")
            try:
                module.close()
            except Exception:
                logger.exception("AppModule.close failed")

    app = FastAPI(
        title="H3 Audit Service",
        description="Audit log for Hexadian Hauling Helper",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    override_jwt_auth(app, jwt_auth)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health_check(request: Request) -> JSONResponse:
        checks: dict[str, dict[str, str | None]] = {
            "mongo": {"status": "ok", "cause": None},
            "subscriber": {"status": "ok", "cause": None},
        }

        # Mongo probe with 2‑second timeout
        try:
            await asyncio.wait_for(motor_client.admin.command("ping"), timeout=2.0)
        except Exception as exc:
            checks["mongo"]["status"] = "degraded"
            checks["mongo"]["cause"] = str(exc) if not isinstance(exc, asyncio.TimeoutError) else "timeout"

        # Subscriber probe
        alive = getattr(request.app.state, "subscriber_alive", True)
        if not alive:
            checks["subscriber"]["status"] = "degraded"
            checks["subscriber"]["cause"] = "subscriber task crashed or not started"

        overall_ok = all(c["status"] == "ok" for c in checks.values())
        body = {
            "status": "ok" if overall_ok else "degraded",
            "service": "hhh-audit-service",
            "checks": checks,
            "cpu_percent": _PROC.cpu_percent(),
            "ram_mb": round(_PROC.memory_info().rss / 1024 / 1024, 1),
            "threads": _PROC.num_threads(),
            "uptime_seconds": round(time.time() - _PROC.create_time()),
        }
        return JSONResponse(content=body, status_code=200 if overall_ok else 503)

    return app


app = create_app()

if __name__ == "__main__":
    _settings = Settings()
    uvicorn.run("src.main:app", host=_settings.host, port=_settings.port, reload=True)
