"Audit event domain model — immutable record of a security-relevant action."

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
