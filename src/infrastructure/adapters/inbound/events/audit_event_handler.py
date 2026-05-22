import logging
from uuid import uuid4

from hhh_events import EventDocument, EventHandler
from pymongo.errors import PyMongoError
from pydantic import ValidationError  # noqa: F401

from src.application.ports.inbound.audit_service import AuditService
from src.domain.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)


class AuditEventHandler(EventHandler):
    """Maps incoming domain events to audit log records."""

    def __init__(self, service: AuditService) -> None:
        self._service = service

    async def handle(self, event: EventDocument) -> int:
        """Persist an audit entry per modified resource; returns count of records written.

        On transient failure (PyMongoError, ConnectionError, TimeoutError) re-raises
        to trigger subscriber retry of the whole event.

        On programmer error (KeyError, AttributeError, ValueError, etc.) also re-raises
        so the subscriber's done_callback can mark the service unhealthy.
        """
        ids = event.modified_ids or [None]
        recorded = 0
        for resource_id in ids:
            try:
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
                recorded += 1
            except (PyMongoError, ConnectionError, TimeoutError):
                logger.exception(
                    "Transient failure persisting audit event for type=%s id=%s",
                    event.type,
                    resource_id,
                )
                raise
            except Exception:
                logger.exception(
                    "Programmer error persisting audit event for type=%s id=%s",
                    event.type,
                    resource_id,
                )
                raise
        logger.debug(
            "AuditEventHandler recorded %d audit event(s) for type=%s",
            recorded,
            event.type,
        )
        return recorded