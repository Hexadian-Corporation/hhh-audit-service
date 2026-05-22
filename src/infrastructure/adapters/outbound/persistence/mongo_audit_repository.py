import logging

from motor.motor_asyncio import AsyncIOMotorCollection

from src.application.ports.outbound.audit_repository import AuditRepository
from src.domain.models.audit_event import AuditEvent
from src.infrastructure.adapters.outbound.persistence.audit_persistence_mapper import AuditPersistenceMapper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "audit_events"


class MongoAuditRepository(AuditRepository):
    """MongoDB time-series implementation of AuditRepository."""

    def __init__(self, collection: AsyncIOMotorCollection, retention_seconds: int) -> None:
        self._collection = collection
        self._retention_seconds = retention_seconds

    async def ensure_timeseries_collection(self) -> None:
        db = self._collection.database
        existing = bool(await db.list_collection_names(filter={"name": COLLECTION_NAME}))
        if existing:
            logger.info("audit_events collection already exists; ensuring retention=%ds", self._retention_seconds)
            try:
                await db.command({"collMod": COLLECTION_NAME, "expireAfterSeconds": self._retention_seconds})
            except Exception:
                logger.exception("collMod failed for audit_events; continuing")
                return
        else:
            logger.info("Creating time-series collection audit_events with retention=%ds", self._retention_seconds)
            await db.create_collection(
                COLLECTION_NAME,
                timeseries={"timeField": "timestamp", "metaField": "metadata", "granularity": "seconds"},
                expireAfterSeconds=self._retention_seconds,
            )

    async def insert(self, event: AuditEvent) -> AuditEvent:
        doc = AuditPersistenceMapper.to_document(event)
        await self._collection.insert_one(doc)
        return event

    async def find_by_id(self, event_id: str) -> AuditEvent | None:
        doc = await self._collection.find_one({"_id": event_id})
        if doc is None:
            return None
        return AuditPersistenceMapper.to_domain(doc)
