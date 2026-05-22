"""Tests for MongoAuditRepository with refactored ensure_timeseries logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import PyMongoError

from src.infrastructure.adapters.outbound.persistence.mongo_audit_repository import (
    COLLECTION_NAME,
    WRONG_SHAPE_MSG,
    MongoAuditRepository,
)
from src.infrastructure.adapters.outbound.persistence.audit_persistence_mapper import AuditPersistenceMapper
from src.domain.models.audit_event import AuditEvent


@pytest.fixture
def mock_db():
    """Mock database with async list_collection_names, create_collection and command."""
    db = MagicMock()
    db.list_collection_names = AsyncMock()
    db.create_collection = AsyncMock()
    db.command = AsyncMock()
    return db


@pytest.fixture
def mock_collection(mock_db):
    """Mock collection with async insert_one, find_one and a reference to mock_db."""
    coll = MagicMock()
    coll.insert_one = AsyncMock()
    coll.find_one = AsyncMock()
    coll.database = mock_db
    return coll


@pytest.fixture
def repo(mock_collection):
    """Default repository instance with 31536000 seconds retention."""
    return MongoAuditRepository(mock_collection, retention_seconds=31_536_000)


@pytest.mark.asyncio
async def test_ensure_timeseries_creates_when_missing(mock_collection, repo):
    mock_collection.database.list_collection_names.return_value = []

    await repo.ensure_timeseries_collection()

    mock_collection.database.list_collection_names.assert_awaited_once()
    mock_collection.database.create_collection.assert_awaited_once_with(
        COLLECTION_NAME,
        timeseries={"timeField": "timestamp", "metaField": "metadata", "granularity": "seconds"},
        expireAfterSeconds=31_536_000,
    )
    mock_collection.database.command.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("retention_seconds", [1, 86400, 31_536_000])
async def test_ensure_timeseries_creates_with_parametrised_retention(
    mock_collection, retention_seconds
):
    mock_collection.database.list_collection_names.return_value = []
    repo = MongoAuditRepository(mock_collection, retention_seconds=retention_seconds)

    await repo.ensure_timeseries_collection()

    mock_collection.database.create_collection.assert_awaited_once()
    call_kwargs = mock_collection.database.create_collection.call_args.kwargs
    assert call_kwargs["expireAfterSeconds"] == retention_seconds
    mock_collection.database.command.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_timeseries_updates_retention_when_exists_and_is_timeseries(
    mock_collection, repo
):
    mock_collection.database.list_collection_names.return_value = [COLLECTION_NAME]
    # first command: listCollections returns valid timeseries
    list_collections_result = {
        "cursor": {"firstBatch": [{"options": {"timeseries": {"timeField": "timestamp"}}}]}
    }
    collmod_result = {"ok": 1}
    mock_collection.database.command.side_effect = [list_collections_result, collmod_result]

    await repo.ensure_timeseries_collection()

    # both commands should be awaited
    assert mock_collection.database.command.await_count == 2

    # first call: listCollections
    first_call_args = mock_collection.database.command.call_args_list[0]
    assert first_call_args[0][0] == {"listCollections": 1, "filter": {"name": COLLECTION_NAME}}

    # second call: collMod
    second_call_args = mock_collection.database.command.call_args_list[1]
    assert second_call_args[0][0] == {
        "collMod": COLLECTION_NAME,
        "expireAfterSeconds": 31_536_000,
    }

    mock_collection.database.create_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_timeseries_raises_when_exists_but_not_timeseries(
    mock_collection, repo
):
    mock_collection.database.list_collection_names.return_value = [COLLECTION_NAME]
    # result without timeseries key
    mock_collection.database.command.return_value = {
        "cursor": {"firstBatch": [{"options": {}}]}
    }

    with pytest.raises(RuntimeError, match=WRONG_SHAPE_MSG):
        await repo.ensure_timeseries_collection()

    # collMod should not be called
    mock_collection.database.command.assert_awaited_once()
    mock_collection.database.create_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_timeseries_raises_when_listcollections_returns_empty_first_batch(
    mock_collection, repo
):
    mock_collection.database.list_collection_names.return_value = [COLLECTION_NAME]
    mock_collection.database.command.return_value = {"cursor": {"firstBatch": []}}

    with pytest.raises(RuntimeError, match=WRONG_SHAPE_MSG):
        await repo.ensure_timeseries_collection()

    mock_collection.database.command.assert_awaited_once()
    mock_collection.database.create_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_timeseries_propagates_pymongoerror_on_collmod(
    mock_collection, repo
):
    mock_collection.database.list_collection_names.return_value = [COLLECTION_NAME]
    # first call OK, second raises PyMongoError
    list_collections_result = {
        "cursor": {"firstBatch": [{"options": {"timeseries": {}}}]}
    }
    mock_collection.database.command.side_effect = [
        list_collections_result,
        PyMongoError("collMod failed"),
    ]

    with pytest.raises(PyMongoError, match="collMod failed"):
        await repo.ensure_timeseries_collection()

    assert mock_collection.database.command.await_count == 2


@pytest.mark.asyncio
async def test_insert_writes_mapped_document_and_returns_event(mock_collection, repo, audit_event):
    expected_doc = AuditPersistenceMapper.to_document(audit_event)

    result = await repo.insert(audit_event)

    mock_collection.insert_one.assert_awaited_once()
    sent_doc = mock_collection.insert_one.call_args[0][0]
    assert sent_doc == expected_doc
    assert sent_doc["_id"] == audit_event.id
    assert sent_doc["metadata"]["resource_type"] == audit_event.resource_type
    assert result == audit_event


@pytest.mark.asyncio
async def test_find_by_id_returns_mapped_domain(mock_collection, repo, audit_event):
    doc = AuditPersistenceMapper.to_document(audit_event)
    mock_collection.find_one.return_value = doc

    result = await repo.find_by_id(audit_event.id)

    mock_collection.find_one.assert_awaited_once_with({"_id": audit_event.id})
    assert result == audit_event


@pytest.mark.asyncio
async def test_find_by_id_returns_none_when_missing(mock_collection, repo, audit_event):
    mock_collection.find_one.return_value = None

    result = await repo.find_by_id(audit_event.id)

    mock_collection.find_one.assert_awaited_once_with({"_id": audit_event.id})
    assert result is None