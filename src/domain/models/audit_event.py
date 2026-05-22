"""Audit event domain model - immutable record of a security-relevant action."""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from src.domain.exceptions.audit_exceptions import InvalidAuditEventError


@dataclass(frozen=True)
class AuditEvent:
    """Append-only audit record. Persisted in a MongoDB time-series collection."""

    id: str
    timestamp: datetime
    resource_type: str
    action: str
    outcome: str
    source_service: str
    actor_id: str | None = None
    actor_email: str | None = None
    resource_id: str | None = None
    client_ip: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate required string fields are non-empty
        for field_name in ("action", "resource_type", "source_service", "outcome"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidAuditEventError(f"{field_name} must not be empty")

        # Replace payload with a read-only mapping proxy
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
