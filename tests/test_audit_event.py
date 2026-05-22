"""Tests for AuditEvent invariants and payload immutability."""

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from src.domain.exceptions.audit_exceptions import InvalidAuditEventError
from src.domain.models.audit_event import AuditEvent


def _kwargs(**overrides):
    base = {
        "id": "evt-1",
        "timestamp": datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
        "resource_type": "contract",
        "action": "contract.created",
        "outcome": "success",
        "source_service": "hhh-contracts-service",
    }
    base.update(overrides)
    return base


def test_audit_event_constructs_with_valid_fields():
    ae = AuditEvent(**_kwargs())
    assert ae.action == "contract.created"
    assert ae.resource_type == "contract"
    assert ae.source_service == "hhh-contracts-service"
    assert ae.outcome == "success"


@pytest.mark.parametrize("field_name", ["action", "resource_type", "source_service", "outcome"])
@pytest.mark.parametrize("bad_value", ["", "   ", "\t\n"])
def test_audit_event_rejects_empty_or_whitespace_required_fields(field_name: str, bad_value: str):
    with pytest.raises(InvalidAuditEventError, match=field_name):
        AuditEvent(**_kwargs(**{field_name: bad_value}))


def test_audit_event_payload_is_frozen_mapping_proxy():
    ae = AuditEvent(**_kwargs(payload={"a": 1, "b": [2, 3]}))
    assert isinstance(ae.payload, MappingProxyType)
    # cannot mutate via the proxy
    with pytest.raises(TypeError):
        ae.payload["c"] = 4  # type: ignore[index]
    # mutating the original dict after construction must not affect the event
    original = {"k": "v"}
    ae2 = AuditEvent(**_kwargs(payload=original))
    original["k"] = "changed"
    assert ae2.payload["k"] == "v"


def test_audit_event_default_payload_is_empty_proxy():
    ae = AuditEvent(**_kwargs())
    assert isinstance(ae.payload, MappingProxyType)
    assert dict(ae.payload) == {}
