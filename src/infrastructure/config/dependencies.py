import contextlib

from hexadian_auth_common.fastapi import JWTAuthDependency
from hhh_events import EventsInfrastructure, EventSubscriber
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from opyoid import Module, SingletonScope

from src.application.ports.inbound.audit_service import AuditService
from src.application.ports.outbound.audit_repository import AuditRepository
from src.application.services.audit_service_impl import AuditServiceImpl
from src.infrastructure.adapters.inbound.events.audit_event_handler import AuditEventHandler
from src.infrastructure.adapters.outbound.persistence.mongo_audit_repository import MongoAuditRepository
from src.infrastructure.config.settings import Settings


class AppModule(Module):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._events_infrastructure: EventsInfrastructure | None = None

    def configure(self) -> None:
        motor_client = AsyncIOMotorClient(self._settings.mongo_uri)
        motor_db = motor_client[self._settings.mongo_db]
        audit_collection: AsyncIOMotorCollection = motor_db["audit_events"]
        retention_seconds = self._settings.retention_days * 86400
        repository = MongoAuditRepository(audit_collection, retention_seconds=retention_seconds)
        service = AuditServiceImpl(repository=repository)
        jwt_auth = JWTAuthDependency(
            jwks_url=self._settings.auth_jwks_url,
            audience=self._settings.auth_audiences,
            issuer=self._settings.auth_issuer,
            leeway_seconds=self._settings.auth_leeway_seconds,
        )
        events_infra = EventsInfrastructure(self._settings.events_mongo_uri, self._settings.events_db)
        self._events_infrastructure = events_infra
        subscriber = events_infra.subscriber(self._settings.subscriber_id)  # subscribe to ALL event types
        handler = AuditEventHandler(service=service)

        self.bind(AsyncIOMotorClient, to_instance=motor_client, scope=SingletonScope)
        self.bind(AsyncIOMotorCollection, to_instance=audit_collection, scope=SingletonScope)
        self.bind(AuditRepository, to_instance=repository, scope=SingletonScope)
        self.bind(AuditService, to_instance=service, scope=SingletonScope)
        self.bind(JWTAuthDependency, to_instance=jwt_auth, scope=SingletonScope)
        self.bind(EventSubscriber, to_instance=subscriber, scope=SingletonScope)
        self.bind(AuditEventHandler, to_instance=handler, scope=SingletonScope)

    def close(self) -> None:
        if self._events_infrastructure is not None:
            with contextlib.suppress(Exception):
                self._events_infrastructure.close()
