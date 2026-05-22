"""Tests for FastAPI lifespan startup and shutdown."""

import asyncio
import importlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.adapters.inbound.events.audit_event_handler import AuditEventHandler


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
        await asyncio.Event().wait()

    fake_subscriber.run = AsyncMock(side_effect=_hang)

    fake_events_infra = MagicMock()
    fake_events_infra.subscriber.return_value = fake_subscriber
    fake_events_infra.close = MagicMock()

    fake_db = _make_fake_db()
    fake_collection = _make_fake_collection(fake_db)

    fake_motor_client = MagicMock()
    fake_motor_client.__getitem__.return_value = fake_db
    fake_motor_client.close = MagicMock()
    fake_db.__getitem__.return_value = fake_collection
    # admin.command for /health mongo ping
    fake_admin = MagicMock()
    fake_admin.command = AsyncMock(return_value={"ok": 1.0})
    fake_motor_client.admin = fake_admin

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


def test_lifespan_starts_subscriber_task_and_passes_handler(patched_app):
    with TestClient(patched_app["app"]) as client:
        client.get("/health")
    patched_app["subscriber"].run.assert_called_once()
    call = patched_app["subscriber"].run.call_args
    handler_arg = call.args[0]
    assert isinstance(handler_arg, AuditEventHandler)
    assert call.kwargs.get("label") == "audit-service"


def test_lifespan_closes_motor_and_events_infra(patched_app):
    with TestClient(patched_app["app"]):
        pass
    patched_app["motor"].close.assert_called_once()
    patched_app["events_infra"].close.assert_called_once()


def test_lifespan_propagates_ensure_timeseries_failure(patched_app):
    # ensure_timeseries_collection failure must propagate so uvicorn fails startup
    patched_app["db"].list_collection_names.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        with TestClient(patched_app["app"]):
            pass


def test_lifespan_swallows_motor_close_failure(patched_app):
    patched_app["motor"].close.side_effect = RuntimeError("close failed")
    with TestClient(patched_app["app"]):
        pass
    patched_app["motor"].close.assert_called_once()


def test_lifespan_swallows_module_close_failure(patched_app):
    patched_app["events_infra"].close.side_effect = RuntimeError("infra close failed")
    with TestClient(patched_app["app"]):
        pass
    # module.close() internally calls events_infra.close; lifespan must catch
    patched_app["events_infra"].close.assert_called_once()


def test_subscriber_crash_marks_alive_false(patched_app):
    patched_app["subscriber"].run.side_effect = RuntimeError("subscriber boom")
    app = patched_app["app"]
    with TestClient(app) as client:
        # Allow event loop a moment to run the failing coroutine and fire done_callback
        for _ in range(20):
            time.sleep(0.05)
            if getattr(app.state, "subscriber_alive", True) is False:
                break
        response = client.get("/health")
    assert app.state.subscriber_alive is False
    assert response.status_code == 503
    assert response.json()["checks"]["subscriber"]["status"] == "degraded"


def test_subscriber_task_cancelled_on_shutdown(patched_app):
    app = patched_app["app"]
    captured: dict = {}
    with TestClient(app):
        captured["task"] = app.state.subscriber_task
    assert captured["task"].cancelled() is True
