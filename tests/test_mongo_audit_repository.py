from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.audit_event import AuditEvent
from src.infrastructure.adapters.outbound.persistence.audit_persistence_mapper import (
    AuditPersistenceMapper,
)
from src.infrastructure.adapters.outbound.persistence.mongo_audit_repository import (
    COLLECTION_NAME,
    MongoAuditRepository,
)


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.list_collection_names = AsyncMock()
    db.create_collection = AsyncMock()
    db.command = AsyncMock()
    return db


@pytest.fixture
def mock_collection(mock_db: MagicMock) -> MagicMock:
    coll = MagicMock()
    coll.insert_one = AsyncMock()
    coll.find_one = AsyncMock()
    coll.database = mock_db
    return coll


@pytest.fixture
def repo(mock_collection: MagicMock) -> MongoAuditRepository:
    return MongoAuditRepository(mock_collection, retention_seconds=31_536_000)


@pytest.mark.asyncio
async def test_ensure_timeseries_creates_when_missing(repo: MongoAuditRepository, mock_db: MagicMock):
    mock_db.list_collection_names.return_value = []
    await repo.ensure_timeseries_collection()
    mock_db.list_collection_names.assert_awaited_once_with(filter={"name": COLLECTION_NAME})
    mock_db.create_collection.assert_awaited_once_with(
        COLLECTION_NAME,
        timeseries={"timeField": "timestamp", "metaField": "metadata", "granularity": "seconds"},
        expireAfterSeconds=31_536_000,
    )
    mock_db.command.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_timeseries_updates_retention_when_exists(repo: MongoAuditRepository, mock_db: MagicMock):
    mock_db.list_collection_names.return_value = [COLLECTION_NAME]
    await repo.ensure_timeseries_collection()
    mock_db.create_collection.assert_not_awaited()
    mock_db.command.assert_awaited_once_with({"collMod": COLLECTION_NAME, "expireAfterSeconds": 31_536_000})


@pytest.mark.asyncio
async def test_ensure_timeseries_swallows_collmod_failure(repo: MongoAuditRepository, mock_db: MagicMock):
    mock_db.list_collection_names.return_value = [COLLECTION_NAME]
    mock_db.command.side_effect = RuntimeError("boom")
    # should NOT raise
    await repo.ensure_timeseries_collection()


@pytest.mark.asyncio
async def test_insert_writes_mapped_document_and_returns_event(
    repo: MongoAuditRepository, mock_collection: MagicMock, audit_event: AuditEvent
):
    result = await repo.insert(audit_event)
    assert result is audit_event
    mock_collection.insert_one.assert_awaited_once()
    sent_doc = mock_collection.insert_one.await_args.args[0]
    assert sent_doc["_id"] == audit_event.id
    assert sent_doc["timestamp"] == audit_event.timestamp
    assert sent_doc["metadata"]["resource_type"] == audit_event.resource_type


@pytest.mark.asyncio
async def test_find_by_id_returns_mapped_domain(
    repo: MongoAuditRepository, mock_collection: MagicMock, audit_event: AuditEvent
):
    mock_collection.find_one.return_value = AuditPersistenceMapper.to_document(audit_event)
    result = await repo.find_by_id(audit_event.id)
    mock_collection.find_one.assert_awaited_once_with({"_id": audit_event.id})
    assert result == audit_event


@pytest.mark.asyncio
async def test_find_by_id_returns_none_when_missing(repo: MongoAuditRepository, mock_collection: MagicMock):
    mock_collection.find_one.return_value = None
    result = await repo.find_by_id("nope")
    assert result is None
