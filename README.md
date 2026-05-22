# hhh-audit-service

Audit log microservice for H³ — captures security-relevant events from all services via MongoDB Change Streams.

## Stack & port

- Port: `8011`
- Stack: Python · FastAPI · MongoDB (time-series) · Motor · opyoid · hhh-events Change Streams · hexadian-auth-common (JWT RS256)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HHH_AUDIT_MONGO_URI` | `mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&readPreference=nearest` | MongoDB connection URI for the audit database |
| `HHH_AUDIT_MONGO_DB` | `hhh_audit` | Name of the audit database |
| `HHH_AUDIT_PORT` | `8011` | Service HTTP port |
| `HHH_AUDIT_HOST` | `0.0.0.0` | Service bind host |
| `HHH_AUDIT_LOG_LEVEL` | `INFO` | Logging level |
| `HHH_AUDIT_AUTH_JWKS_URL` | (required) | JWKS endpoint for JWT verification |
| `HHH_AUDIT_AUTH_ISSUER` | (required) | Expected JWT issuer |
| `HHH_AUDIT_AUTH_AUDIENCES` | (required, comma-separated) | Allowed JWT audiences |
| `HHH_AUDIT_AUTH_LEEWAY_SECONDS` | `30` | Clock leeway for JWT validation |
| `HHH_AUDIT_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:3001"]` | Allowed CORS origins |
| `HHH_AUDIT_RETENTION_DAYS` | `365` | MongoDB TTL for audit_events documents |
| `HHH_AUDIT_EVENTS_MONGO_URI` | `mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&readPreference=nearest` | MongoDB connection URI for the events database (Change Stream source) |
| `HHH_AUDIT_EVENTS_DB` | `hhh_events` | Name of the events database |
| `HHH_AUDIT_EVENTS_COLLECTION` | `events` | Name of the events collection |
| `HHH_AUDIT_SUBSCRIBER_ID` | `hhh-audit-service` | Unique ID for Change Stream subscription |

## MongoDB collection

The `audit_events` collection is a time-series collection with `timeField=timestamp`, `metaField=metadata`, `granularity=seconds`. A TTL index on `timestamp` with `expireAfterSeconds = HHH_AUDIT_RETENTION_DAYS * 86400` is created on startup if missing.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health probe |

> **Note:** Read endpoints are reserved for a future PR; permission `hhh:audit:read` is registered for them.

## Tooling

| Action | Command |
|---|---|
| Setup | `uv sync --all-extras` |
| Run (dev) | `uv run uvicorn src.main:app --reload --port 8011` |
| Test | `uv run pytest --cov --cov-fail-under=90` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |

## Out of scope for the bootstrap PR

- CSV export
- GDPR erasure endpoint
- HMAC tamper chain
- Signed-IP verification
- PII anonymisation
- Async export jobs
- WebSocket streaming

(Tracked separately per ADR-0003.)

## License

PolyForm Noncommercial 1.0.0 (Modified) — Copyright (C) 2026 Hexadian Corporation.
