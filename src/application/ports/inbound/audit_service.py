"""Inbound port: AuditService use cases."""

from abc import ABC, abstractmethod

from src.domain.models.audit_event import AuditEvent


class AuditService(ABC):
    @abstractmethod
    async def record_event(self, event: AuditEvent) -> AuditEvent:
        """Persist an audit event and return the stored record."""
        ...  # pragma: no cover

    @abstractmethod
    async def get_event_by_id(self, event_id: str) -> AuditEvent:
        """Fetch a previously recorded event by its id. Raises AuditEventNotFoundError if missing."""
        ...  # pragma: no cover
