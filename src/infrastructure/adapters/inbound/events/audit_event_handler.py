import logging
from uuid import uuid4

from hhh_events import EventDocument, EventHandler

from src.application.ports.inbound.audit_service import AuditService
from src.domain.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)


class AuditEventHandler(EventHandler):
    """Maps incoming domain events to audit log records."""

    def __init__(self, service: AuditService) -> None:
        self._service = service

    async def handle(self, event: EventDocument) -> int:
        """Persist an audit entry per modified resource; returns count of records written."""
        ids = event.modified_ids or [None]
        try:
            for resource_id in ids:
                audit_event = AuditEvent(
                    id=str(uuid4()),
                    timestamp=event.timestamp,
                    resource_type=event.type,
                    action=event.type,
                    outcome="success",
                    source_service=event.source_service,
                    resource_id=resource_id,
                    payload={
                        "mode": event.mode.value,
                        "metadata": event.metadata,
                        "retry_count": event.retry_count,
                    },
                )
                await self._service.record_event(audit_event)
            logger.debug(
                "AuditEventHandler recorded %d audit event(s) for type=%s",
                len(ids),
                event.type,
            )
            return len(ids)
        except Exception:
            logger.exception("AuditEventHandler failed for event type=%s", event.type)
            return 0
