"""Implementation of AuditService — delegates persistence to AuditRepository."""

from src.application.ports.inbound.audit_service import AuditService
from src.application.ports.outbound.audit_repository import AuditRepository
from src.domain.exceptions.audit_exceptions import AuditEventNotFoundError
from src.domain.models.audit_event import AuditEvent


class AuditServiceImpl(AuditService):
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def record_event(self, event: AuditEvent) -> AuditEvent:
        return await self._repository.insert(event)

    async def get_event_by_id(self, event_id: str) -> AuditEvent:
        event = await self._repository.find_by_id(event_id)
        if event is None:
            raise AuditEventNotFoundError(f"AuditEvent {event_id!r} not found")
        return event
