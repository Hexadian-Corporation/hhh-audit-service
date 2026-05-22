from fastapi import APIRouter

from src.application.ports.inbound.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])

_service: AuditService | None = None


def init_router(service: AuditService) -> None:
    global _service
    _service = service


# TODO(ADR-0003): wire read endpoints once API surface is approved:
#   - GET /audit/events       (list / search; permission=require_permission("hhh:audit:read"))
#   - GET /audit/events/{id}  (lookup;        permission=require_permission("hhh:audit:read"))
#   - GET /audit/export.csv   (CSV export;    permission=require_permission("hhh:audit:export"))
# Until then, only the events-subscriber ingest pipeline writes to MongoDB.
