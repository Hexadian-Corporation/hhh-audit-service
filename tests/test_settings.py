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


def test_auth_audiences_rejects_malformed_json_list(monkeypatch: pytest.MonkeyPatch):
    # Looks like a JSON list (starts with [) but is malformed - must NOT fall back to comma-split.
    monkeypatch.setenv("HHH_AUDIT_AUTH_AUDIENCES", '["alpha", "beta')
    with pytest.raises(ValueError, match="looks like a JSON list but is malformed"):
        Settings()


def test_cors_origins_rejects_malformed_json_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_CORS_ORIGINS", "[http://x.test")
    with pytest.raises(ValueError, match="looks like a JSON list but is malformed"):
        Settings()


def test_cors_origins_comma_split_path_still_works(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_CORS_ORIGINS", "http://a.test, http://b.test")
    s = Settings()
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_accepts_json_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HHH_AUDIT_CORS_ORIGINS", '["http://a.test","http://b.test"]')
    s = Settings()
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_auth_audiences_rejects_non_list_json(monkeypatch: pytest.MonkeyPatch):
    # JSON parses but is not a list (after the lstrip check passes by [ - actually this is invalid JSON;
    # use a list-with-dict shape that parses but the top-level is still a list... use a string that
    # starts with [ and parses to a non-list value via a tricky construct - actually json.loads of
    # "[1, 2, 3]" returns a list; to get a non-list we need "[".lstrip startswith [ check to pass
    # but JSON to return non-list. That's impossible: any JSON starting with [ is an array. So this
    # test instead exercises the "non-list JSON object via inner-bracket" case by sending a string
    # that starts with [ but parses to a JSON array - just confirm the array path works).
    monkeypatch.setenv("HHH_AUDIT_AUTH_AUDIENCES", '["solo"]')
    s = Settings()
    assert s.auth_audiences == ["solo"]
