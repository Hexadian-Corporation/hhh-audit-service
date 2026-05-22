from datetime import UTC, datetime

from src.infrastructure.adapters.outbound.persistence.audit_persistence_mapper import AuditPersistenceMapper


def test_to_document_includes_timeseries_metafield(audit_event):
    doc = AuditPersistenceMapper.to_document(audit_event)
    assert doc["_id"] == audit_event.id
    assert doc["timestamp"] == audit_event.timestamp
    assert "metadata" in doc
    assert doc["metadata"]["resource_type"] == audit_event.resource_type
    assert doc["metadata"]["action"] == audit_event.action
    assert doc["metadata"]["source_service"] == audit_event.source_service
    assert doc["metadata"]["actor_id"] == audit_event.actor_id
    assert doc["metadata"]["resource_id"] == audit_event.resource_id
    assert doc["payload"] == audit_event.payload
    assert doc["client_ip"] == audit_event.client_ip
    assert doc["outcome"] == audit_event.outcome
    assert doc["actor_email"] == audit_event.actor_email


def test_to_domain_round_trip(audit_event):
    doc = AuditPersistenceMapper.to_document(audit_event)
    roundtrip = AuditPersistenceMapper.to_domain(doc)
    assert roundtrip == audit_event


def test_to_domain_casts_objectid_to_str():
    # simulate a BSON ObjectId-like value (object whose str() differs)
    class FakeOid:
        def __str__(self) -> str:
            return "507f1f77bcf86cd799439011"

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    doc = {
        "_id": FakeOid(),
        "timestamp": ts,
        "resource_type": "r",
        "action": "a",
        "outcome": "success",
        "source_service": "svc",
    }
    e = AuditPersistenceMapper.to_domain(doc)
    assert e.id == "507f1f77bcf86cd799439011"
    assert isinstance(e.id, str)
    assert e.payload == {}
    assert e.actor_id is None
    assert e.client_ip is None


def test_to_domain_missing_optional_fields_become_none():
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    doc = {
        "_id": "x",
        "timestamp": ts,
        "resource_type": "r",
        "action": "a",
        "outcome": "success",
        "source_service": "svc",
        "payload": {"k": 1},
    }
    e = AuditPersistenceMapper.to_domain(doc)
    assert e.actor_id is None and e.actor_email is None and e.resource_id is None and e.client_ip is None
    assert e.payload == {"k": 1}
