from unittest.mock import AsyncMock

import pytest

from src.application.ports.outbound.audit_repository import AuditRepository
from src.application.services.audit_service_impl import AuditServiceImpl
from src.domain.exceptions.audit_exceptions import AuditEventNotFoundError


class _DummyAuditEvent:
    def __init__(self, id):
        self.id = id


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock(spec=AuditRepository)


@pytest.fixture
def service(mock_repository) -> AuditServiceImpl:
    return AuditServiceImpl(repository=mock_repository)


@pytest.fixture
def audit_event():
    return _DummyAuditEvent(id="test-id")


@pytest.mark.asyncio
async def test_record_event_delegates_to_repository(service, mock_repository, audit_event):
    mock_repository.insert.return_value = audit_event
    result = await service.record_event(audit_event)
    assert result is audit_event
    mock_repository.insert.assert_awaited_once_with(audit_event)


@pytest.mark.asyncio
async def test_get_event_by_id_returns_event(service, mock_repository, audit_event):
    mock_repository.find_by_id.return_value = audit_event
    result = await service.get_event_by_id(audit_event.id)
    assert result is audit_event
    mock_repository.find_by_id.assert_awaited_once_with(audit_event.id)


@pytest.mark.asyncio
async def test_get_event_by_id_raises_when_missing(service, mock_repository):
    mock_repository.find_by_id.return_value = None
    with pytest.raises(AuditEventNotFoundError, match="missing-id"):
        await service.get_event_by_id("missing-id")
