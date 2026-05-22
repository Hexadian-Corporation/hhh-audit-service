"""Outbound port: AuditRepository — persistence contract for audit events."""

from abc import ABC, abstractmethod

from src.domain.models.audit_event import AuditEvent


class AuditRepository(ABC):
    @abstractmethod
    async def ensure_timeseries_collection(self) -> None:
        """Create the audit_events time-series collection and TTL index if they don't already exist. Idempotent."""
        ...  # pragma: no cover

    @abstractmethod
    async def insert(self, event: AuditEvent) -> AuditEvent:
        """Insert a new audit event and return the persisted record."""
        ...  # pragma: no cover

    @abstractmethod
    async def find_by_id(self, event_id: str) -> AuditEvent | None:
        """Return the event with the given id or None if not found."""
        ...  # pragma: no cover
