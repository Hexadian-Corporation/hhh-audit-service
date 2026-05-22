"""Shared pytest fixtures for hhh-audit-service tests."""

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest import MonkeyPatch
from pytest_httpserver import HTTPServer

TEST_AUDIENCES = ["hexadian-hhh", "hexadian-hhh-admin"]
TEST_ISSUER = "https://auth.hexadian.com"


@pytest.fixture(autouse=True, scope="session")
def _set_required_env_vars() -> Any:
    """Provide minimum required Settings env vars for the test session.

    Uses a session-scoped MonkeyPatch context manager so changes are reverted
    after the run instead of mutating os.environ at import time (which would
    leak into other test runners and obscure missing-env-var bugs).
    """
    mp = MonkeyPatch()
    mp.setenv("HHH_AUDIT_AUTH_JWKS_URL", "https://auth.example.test/.well-known/jwks.json")
    mp.setenv("HHH_AUDIT_AUTH_ISSUER", TEST_ISSUER)
    mp.setenv("HHH_AUDIT_AUTH_AUDIENCES", ",".join(TEST_AUDIENCES))
    try:
        yield
    finally:
        mp.undo()


def _int_to_base64url(num: int) -> str:
    byte_length = (num.bit_length() + 7) // 8
    num_bytes = num.to_bytes(byte_length or 1, byteorder="big")
    return base64.urlsafe_b64encode(num_bytes).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class RsaKeypair:
    private_pem: bytes
    public_pem: bytes
    jwk: dict[str, Any]
    kid: str

    def __post_init__(self) -> None:
        if self.kid != self.jwk.get("kid"):
            raise ValueError(f"Mismatched kid: {self.kid!r} != {self.jwk.get('kid')!r}")


@pytest.fixture(scope="session")
def rsa_keypair() -> RsaKeypair:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_numbers = public_key.public_numbers()
    kid = "test-key-1"
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _int_to_base64url(public_numbers.n),
        "e": _int_to_base64url(public_numbers.e),
    }
    return RsaKeypair(private_pem=private_pem, public_pem=public_pem, jwk=jwk, kid=kid)


@pytest.fixture(scope="session")
def jwks_document(rsa_keypair: RsaKeypair) -> dict[str, Any]:
    return {"keys": [rsa_keypair.jwk]}


@pytest.fixture
def rs256_token_factory(rsa_keypair: RsaKeypair) -> Callable:
    private_key = serialization.load_pem_private_key(rsa_keypair.private_pem, password=None, backend=default_backend())

    def _make(
        *,
        sub: str = "user-1",
        permissions: list[str] | None = None,
        aud: str = "hexadian-hhh",
        iss: str = TEST_ISSUER,
        exp_offset: int = 300,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": sub,
            "aud": aud,
            "iss": iss,
            "iat": now,
            "exp": now + exp_offset,
        }
        if permissions is not None:
            payload["permissions"] = permissions
        if extra_claims:
            payload.update(extra_claims)
        headers = {"kid": rsa_keypair.kid}
        return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)

    return _make


@pytest.fixture
def jwks_server(httpserver: HTTPServer, jwks_document: dict) -> HTTPServer:
    assert "keys" in jwks_document and jwks_document["keys"], "Empty JWKS"
    httpserver.expect_request("/.well-known/jwks.json").respond_with_json(
        jwks_document, status=200, content_type="application/json"
    )
    return httpserver


@pytest.fixture
def jwks_url(jwks_server: HTTPServer) -> str:
    return jwks_server.url_for("/.well-known/jwks.json")


@pytest.fixture
def audit_event():
    from src.domain.models.audit_event import AuditEvent

    return AuditEvent(
        id="evt-test-001",
        timestamp=datetime(2026, 1, 15, 12, 30, 45, tzinfo=UTC),
        resource_type="contract",
        action="contract.created",
        outcome="success",
        source_service="hhh-contracts-service",
        actor_id="user-42",
        actor_email="user@example.test",
        resource_id="contract-123",
        client_ip="203.0.113.42",
        payload={"mode": "incremental", "metadata": {"k": "v"}, "retry_count": 0},
    )
