from typing import Any

from src.domain.models.audit_event import AuditEvent


class AuditPersistenceMapper:
    """Mapper between AuditEvent domain dataclass and MongoDB documents."""

    @staticmethod
    def to_domain(doc: dict[str, Any]) -> AuditEvent:
        """Map a MongoDB document dict to an AuditEvent instance."""
        event_id = str(doc["_id"])
        timestamp = doc["timestamp"]
        resource_type = doc["resource_type"]
        action = doc["action"]
        outcome = doc["outcome"]
        source_service = doc["source_service"]
        actor_id = doc.get("actor_id")
        actor_email = doc.get("actor_email")
        resource_id = doc.get("resource_id")
        client_ip = doc.get("client_ip")
        payload = doc.get("payload", {})
        return AuditEvent(
            id=event_id,
            timestamp=timestamp,
            resource_type=resource_type,
            action=action,
            outcome=outcome,
            source_service=source_service,
            actor_id=actor_id,
            actor_email=actor_email,
            resource_id=resource_id,
            client_ip=client_ip,
            payload=payload,
        )

    @staticmethod
    def to_document(event: AuditEvent) -> dict[str, Any]:
        """Map an AuditEvent to a MongoDB document dict, keeping timestamp and metadata for time-series."""
        return {
            "_id": event.id,
            "timestamp": event.timestamp,
            "metadata": {
                "resource_type": event.resource_type,
                "action": event.action,
                "source_service": event.source_service,
                "actor_id": event.actor_id,
                "resource_id": event.resource_id,
            },
            "resource_type": event.resource_type,
            "action": event.action,
            "outcome": event.outcome,
            "source_service": event.source_service,
            "actor_id": event.actor_id,
            "actor_email": event.actor_email,
            "resource_id": event.resource_id,
            "client_ip": event.client_ip,
            "payload": dict(event.payload),
        }
