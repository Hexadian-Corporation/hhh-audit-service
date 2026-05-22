"""Audit service domain exceptions."""


class AuditError(Exception):
    """Base class for all audit service domain errors."""


class AuditEventNotFoundError(AuditError):
    """Raised when an audit event lookup by id returns no document."""


class InvalidAuditEventError(AuditError):
    """Raised when an incoming event cannot be transformed into a valid AuditEvent."""
