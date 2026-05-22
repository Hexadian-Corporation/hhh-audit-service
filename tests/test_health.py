"""Tests for the /health probe endpoint."""

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
            "motor": fake_motor_client,
            "admin": fake_admin,
            "subscriber": fake_subscriber,
        }

    import src.infrastructure.config.dependencies as deps_module

    importlib.reload(deps_module)
    import src.main as main_module

    importlib.reload(main_module)


def test_health_returns_200_when_all_ok(patched_app):
    with TestClient(patched_app["app"]) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "hhh-audit-service"
    assert body["checks"]["mongo"]["status"] == "ok"
    assert body["checks"]["mongo"]["cause"] is None
    assert body["checks"]["subscriber"]["status"] == "ok"
    assert body["checks"]["subscriber"]["cause"] is None
    for key in ("cpu_percent", "ram_mb", "threads", "uptime_seconds"):
        assert key in body


def test_health_no_auth_required(patched_app):
    with TestClient(patched_app["app"]) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_503_when_mongo_ping_fails(patched_app):
    patched_app["admin"].command.side_effect = RuntimeError("connection refused")
    with TestClient(patched_app["app"]) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["mongo"]["status"] == "degraded"
    assert "connection refused" in (body["checks"]["mongo"]["cause"] or "")
    assert body["checks"]["subscriber"]["status"] == "ok"


def test_health_returns_503_when_mongo_ping_times_out(patched_app):
    patched_app["admin"].command.side_effect = asyncio.TimeoutError
    with TestClient(patched_app["app"]) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["mongo"]["status"] == "degraded"
    assert body["checks"]["mongo"]["cause"] == "timeout"


def test_health_returns_503_when_subscriber_dead(patched_app):
    app = patched_app["app"]
    with TestClient(app) as client:
        app.state.subscriber_alive = False
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["subscriber"]["status"] == "degraded"
    assert body["checks"]["mongo"]["status"] == "ok"
