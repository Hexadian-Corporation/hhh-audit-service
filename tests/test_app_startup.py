import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_fake_db() -> MagicMock:
    db = MagicMock()
    db.list_collection_names = AsyncMock(return_value=[])
    db.create_collection = AsyncMock()
    db.command = AsyncMock()
    return db


def _make_fake_collection(db: MagicMock) -> MagicMock:
    coll = MagicMock()
    coll.insert_one = AsyncMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.database = db
    return coll


@pytest.fixture
def patched_app():
    fake_subscriber = MagicMock()

    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(3600)

    fake_subscriber.run = AsyncMock(side_effect=_hang)

    fake_events_infra = MagicMock()
    fake_events_infra.subscriber.return_value = fake_subscriber
    fake_events_infra.close = MagicMock()

    fake_db = _make_fake_db()
    fake_collection = _make_fake_collection(fake_db)

    fake_motor_client = MagicMock()
    # motor_client[db_name] -> fake_db
    fake_motor_client.__getitem__.return_value = fake_db
    fake_motor_client.close = MagicMock()
    # fake_db[collection_name] -> fake_collection
    fake_db.__getitem__.return_value = fake_collection

    fake_jwt_instance = MagicMock()

    motor_client_cls = MagicMock(return_value=fake_motor_client)
    events_infra_cls = MagicMock(return_value=fake_events_infra)
    jwt_dep_cls = MagicMock(return_value=fake_jwt_instance)

    with (
        patch("motor.motor_asyncio.AsyncIOMotorClient", motor_client_cls),
        patch("hexadian_auth_common.fastapi.JWTAuthDependency", jwt_dep_cls),
        patch("hhh_events.EventsInfrastructure", events_infra_cls),
        patch("hhh_events.infrastructure.EventsInfrastructure", events_infra_cls),
    ):
        import src.infrastructure.config.dependencies as deps_module

        importlib.reload(deps_module)
        import src.main as main_module

        importlib.reload(main_module)
        yield {
            "app": main_module.app,
            "db": fake_db,
            "collection": fake_collection,
            "subscriber": fake_subscriber,
            "motor": fake_motor_client,
            "events_infra": fake_events_infra,
        }

    import src.infrastructure.config.dependencies as deps_module

    importlib.reload(deps_module)
    import src.main as main_module

    importlib.reload(main_module)


def test_lifespan_calls_ensure_timeseries_collection(patched_app):
    with TestClient(patched_app["app"]) as client:
        r = client.get("/health")
        assert r.status_code == 200
    patched_app["db"].list_collection_names.assert_awaited()
    patched_app["db"].create_collection.assert_awaited()


def test_lifespan_starts_subscriber_task(patched_app):
    with TestClient(patched_app["app"]) as client:
        client.get("/health")
    patched_app["subscriber"].run.assert_called_once()
    call = patched_app["subscriber"].run.call_args
    assert call.kwargs.get("label") == "audit-service"


def test_lifespan_closes_motor_and_events_infra(patched_app):
    with TestClient(patched_app["app"]):
        pass
    patched_app["motor"].close.assert_called_once()
    patched_app["events_infra"].close.assert_called_once()


def test_lifespan_swallows_ensure_timeseries_failure(patched_app):
    # make list_collection_names raise -> ensure_timeseries_collection raises
    # -> lifespan must catch and continue
    patched_app["db"].list_collection_names.side_effect = RuntimeError("boom")
    with TestClient(patched_app["app"]) as client:
        r = client.get("/health")
        assert r.status_code == 200


def test_lifespan_swallows_motor_close_failure(patched_app):
    patched_app["motor"].close.side_effect = RuntimeError("close failed")
    with TestClient(patched_app["app"]):
        pass
    patched_app["motor"].close.assert_called_once()
