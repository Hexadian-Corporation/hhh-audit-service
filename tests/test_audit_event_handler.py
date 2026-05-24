"""Tests for AuditEventHandler with narrowed exception handling."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from hhh_events import EventDocument, EventMode
from pymongo.errors import PyMongoError

from src.application.ports.inbound.audit_service import AuditService
from src.domain.models.audit_event import AuditEvent
from src.infrastructure.adapters.inbound.events.audit_event_handler import AuditEventHandler


@pytest.fixture
def mock_service() -> AsyncMock:
    service = AsyncMock(spec=AuditService)
    service.record_event.return_value = None
    return service


@pytest.fixture
def handler(mock_service: AsyncMock) -> AuditEventHandler:
    return AuditEventHandler(service=mock_service)


def _make_event(
    ids: list[str] | list[None] | list,
    event_type: str = "contract.created",
    actor_id: str | None = None,
    actor_email: str | None = None,
    client_ip: str | None = None,
) -> EventDocument:
    return EventDocument(
        type=event_type,
        source_service="hhh-contracts-service",
        modified_ids=ids,
        mode=EventMode.INCREMENTAL,
        timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
        metadata={"x": 1},
        retry_count=0,
        actor_id=actor_id,
        actor_email=actor_email,
        client_ip=client_ip,
    )


@pytest.mark.asyncio
async def test_handle_writes_one_audit_event_per_modified_id(
    handler: AuditEventHandler, mock_service: AsyncMock
) -> None:
    event = _make_event(["id-1", "id-2", "id-3"])
    count = await handler.handle(event)
    assert count == 3
    assert mock_service.record_event.await_count == 3
    persisted = [c.args[0] for c in mock_service.record_event.await_args_list]
    assert {p.resource_id for p in persisted} == {"id-1", "id-2", "id-3"}
    for ae in persisted:
        assert isinstance(ae, AuditEvent)
        assert ae.resource_type == "contract.created"
        assert ae.action == "contract.created"
        assert ae.outcome == "success"
        assert ae.source_service == "hhh-contracts-service"
        assert ae.timestamp == event.timestamp
        assert ae.payload == {"mode": "incremental", "metadata": {"x": 1}, "retry_count": 0}
        assert ae.actor_id is None
        assert ae.actor_email is None
        assert ae.client_ip is None


@pytest.mark.asyncio
async def test_handle_with_empty_modified_ids_writes_single_event(
    handler: AuditEventHandler, mock_service: AsyncMock
) -> None:
    event = EventDocument(
        type="system.heartbeat",
        source_service="hhh-contracts-service",
        modified_ids=[],
        mode=EventMode.FULL_SYNC,
        timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
        metadata={},
        retry_count=0,
    )
    count = await handler.handle(event)
    assert count == 1
    ae = mock_service.record_event.await_args.args[0]
    assert ae.resource_id is None
    assert ae.payload == {"mode": "full_sync", "metadata": {}, "retry_count": 0}


@pytest.mark.asyncio
async def test_handle_ids_are_unique_uuids(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    event = _make_event(["a", "b"], event_type="x.y")
    await handler.handle(event)
    persisted = [c.args[0] for c in mock_service.record_event.await_args_list]
    ids = {p.id for p in persisted}
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_handle_reraises_on_pymongoerror_and_stops_after_first_failure(
    handler: AuditEventHandler, mock_service: AsyncMock
) -> None:
    mock_service.record_event.side_effect = PyMongoError("transient db error")
    event = _make_event(["id-1", "id-2", "id-3"])
    with pytest.raises(PyMongoError, match="transient"):
        await handler.handle(event)
    assert mock_service.record_event.await_count == 1


@pytest.mark.asyncio
async def test_handle_reraises_on_connection_error(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    mock_service.record_event.side_effect = ConnectionError("connection refused")
    event = _make_event(["id-1", "id-2"])
    with pytest.raises(ConnectionError, match="connection refused"):
        await handler.handle(event)
    assert mock_service.record_event.await_count == 1


@pytest.mark.asyncio
async def test_handle_reraises_on_timeout_error(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    mock_service.record_event.side_effect = TimeoutError("timeout")
    event = _make_event(["id-1"])
    with pytest.raises(TimeoutError, match="timeout"):
        await handler.handle(event)
    assert mock_service.record_event.await_count == 1


@pytest.mark.asyncio
async def test_handle_reraises_on_programmer_value_error(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    mock_service.record_event.side_effect = ValueError("bad payload")
    event = _make_event(["id-1"])
    with pytest.raises(ValueError, match="bad payload"):
        await handler.handle(event)
    assert mock_service.record_event.await_count == 1


@pytest.mark.asyncio
async def test_handle_reraises_on_runtime_error(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    mock_service.record_event.side_effect = RuntimeError("db down")
    event = _make_event(["id-1"])
    with pytest.raises(RuntimeError, match="db down"):
        await handler.handle(event)
    assert mock_service.record_event.await_count == 1


@pytest.mark.asyncio
async def test_handle_propagates_actor_fields(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    event = _make_event(
        ["resource-1"],
        actor_id="user-1",
        actor_email="user@example.com",
        client_ip="10.0.0.1",
    )
    await handler.handle(event)
    ae: AuditEvent = mock_service.record_event.await_args.args[0]
    assert ae.actor_id == "user-1"
    assert ae.actor_email == "user@example.com"
    assert ae.client_ip == "10.0.0.1"
