import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psutil
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hexadian_auth_common.fastapi import JWTAuthDependency, _stub_jwt_auth, register_exception_handlers
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
        # startup: ensure the time-series collection + TTL are in place before subscriber starts
        try:
            await repository.ensure_timeseries_collection()
        except Exception:
            logger.exception("Failed to ensure audit_events collection; continuing")
        # spawn the events subscriber as a background task
        task = asyncio.create_task(subscriber.run(handler, label="audit-service"))
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
            module.close()

    app = FastAPI(
        title="H³ Audit Service",
        description="Audit log for Hexadian Hauling Helper",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.dependency_overrides[_stub_jwt_auth] = jwt_auth
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)

    @app.get("/health", tags=["health"])
    def health_check() -> dict:
        return {
            "status": "ok",
            "service": "hhh-audit-service",
            "cpu_percent": _PROC.cpu_percent(),
            "ram_mb": round(_PROC.memory_info().rss / 1024 / 1024, 1),
            "threads": _PROC.num_threads(),
            "uptime_seconds": round(time.time() - _PROC.create_time()),
        }

    return app


app = create_app()

if __name__ == "__main__":
    _settings = Settings()
    uvicorn.run("src.main:app", host=_settings.host, port=_settings.port, reload=True)
