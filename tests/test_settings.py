import pytest

from src.infrastructure.config.settings import Settings


def test_settings_loads_with_required_env_vars():
    s = Settings()
    assert s.mongo_db == "hhh_audit"
    assert s.port == 8011
    assert s.host == "0.0.0.0"
    assert s.log_level == "INFO"
    assert s.retention_days == 365
    assert s.events_db == "hhh_events"
    assert s.events_collection == "events"
    assert s.subscriber_id == "hhh-audit-service"
    assert s.auth_audiences == ["hexadian-hhh", "hexadian-hhh-admin"]


def test_settings_env_prefix_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_MONGO_DB", "custom_db")
    monkeypatch.setenv("HHH_AUDIT_PORT", "9000")
    monkeypatch.setenv("HHH_AUDIT_RETENTION_DAYS", "7")
    s = Settings()
    assert s.mongo_db == "custom_db"
    assert s.port == 9000
    assert s.retention_days == 7


def test_log_level_validator_normalises_to_upper(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_LOG_LEVEL", "debug")
    s = Settings()
    assert s.log_level == "DEBUG"


def test_log_level_validator_rejects_invalid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_LOG_LEVEL", "chatty")
    with pytest.raises(ValueError, match="log_level"):
        Settings()


def test_auth_audiences_parses_comma_separated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_AUTH_AUDIENCES", "a, b,c")
    s = Settings()
    assert s.auth_audiences == ["a", "b", "c"]


def test_auth_audiences_rejects_empty_comma_string(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_AUTH_AUDIENCES", ", , ,")
    with pytest.raises(ValueError, match="auth_audiences"):
        Settings()


def test_auth_audiences_accepts_json_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_AUTH_AUDIENCES", '["alpha","beta"]')
    s = Settings()
    assert s.auth_audiences == ["alpha", "beta"]


def test_retention_days_must_be_positive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_RETENTION_DAYS", "0")
    with pytest.raises(ValueError):
        Settings()
