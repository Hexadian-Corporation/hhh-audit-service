from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from src.domain.exceptions.audit_exceptions import AuditError, AuditEventNotFoundError, InvalidAuditEventError
from src.domain.models.audit_event import AuditEvent


def test_audit_event_minimal_construction():
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    e = AuditEvent(id="a", timestamp=ts, resource_type="r", action="a", outcome="success", source_service="svc")
    assert e.id == "a"
    assert e.actor_id is None
    assert e.actor_email is None
    assert e.resource_id is None
    assert e.client_ip is None
    assert e.payload == {}


def test_audit_event_is_frozen(audit_event):
    with pytest.raises(FrozenInstanceError):
        audit_event.id = "changed"  # type: ignore[misc]


def test_audit_event_payload_factory_is_independent():
    # Payload is now an immutable MappingProxyType; assert both default payloads are empty
    # and that they are distinct objects (no shared mutable default).
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    a = AuditEvent(id="1", timestamp=ts, resource_type="r", action="a", outcome="success", source_service="s")
    b = AuditEvent(id="2", timestamp=ts, resource_type="r", action="a", outcome="success", source_service="s")
    assert dict(a.payload) == {}
    assert dict(b.payload) == {}
    assert a.payload is not b.payload


def test_audit_event_not_found_is_audit_error():
    assert issubclass(AuditEventNotFoundError, AuditError)
    assert issubclass(AuditError, Exception)


def test_invalid_audit_event_is_audit_error():
    assert issubclass(InvalidAuditEventError, AuditError)


def test_audit_error_can_be_raised_with_message():
    with pytest.raises(AuditEventNotFoundError, match="missing"):
        raise AuditEventNotFoundError("missing id 42")
