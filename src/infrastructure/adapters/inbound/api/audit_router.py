from fastapi import APIRouter
from hexadian_auth_common.fastapi import require_permission

from src.application.ports.inbound.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])

_service: AuditService | None = None

_read = require_permission("hhh:audit:read")  # reserved for read endpoints in a future PR (ADR-0003)


def init_router(service: AuditService) -> None:
    global _service
    _service = service


# TODO(ADR-0003): wire read endpoints once API surface is approved:
#   - GET /audit/events       (list / search; permission=_read)
#   - GET /audit/events/{id}  (lookup;        permission=_read)
#   - GET /audit/export.csv   (CSV export;    permission=hhh:audit:export)
# Until then, only the events-subscriber ingest pipeline writes to MongoDB.
