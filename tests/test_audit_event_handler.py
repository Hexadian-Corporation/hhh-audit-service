from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from hhh_events import EventDocument, EventMode

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


@pytest.mark.asyncio
async def test_handle_writes_one_audit_event_per_modified_id(
    handler: AuditEventHandler, mock_service: AsyncMock
) -> None:
    event = EventDocument(
        type="contract.created",
        source_service="hhh-contracts-service",
        modified_ids=["id-1", "id-2", "id-3"],
        mode=EventMode.INCREMENTAL,
        timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
        metadata={"x": 1},
        retry_count=0,
    )
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
async def test_handle_returns_zero_on_failure_and_does_not_raise(
    handler: AuditEventHandler, mock_service: AsyncMock
) -> None:
    mock_service.record_event.side_effect = RuntimeError("db down")
    event = EventDocument(
        type="contract.created",
        source_service="hhh-contracts-service",
        modified_ids=["id-1"],
        mode=EventMode.INCREMENTAL,
        timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
        metadata={},
        retry_count=0,
    )
    count = await handler.handle(event)
    assert count == 0


@pytest.mark.asyncio
async def test_handle_ids_are_unique_uuids(handler: AuditEventHandler, mock_service: AsyncMock) -> None:
    event = EventDocument(
        type="x.y",
        source_service="svc",
        modified_ids=["a", "b"],
        mode=EventMode.INCREMENTAL,
        timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
        metadata={},
        retry_count=0,
    )
    await handler.handle(event)
    persisted = [c.args[0] for c in mock_service.record_event.await_args_list]
    ids = {p.id for p in persisted}
    assert len(ids) == 2
