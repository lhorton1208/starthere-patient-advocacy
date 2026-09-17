"""JWKS helpers for the StartHere Patient/Advocate Portal.

Publishes the public key set at /.well-known/jwks.json for vendor registration
(jwks_uri / JKU). The matching private key signs Epic Backend OAuth JWTs
(private_key_jwt client_assertion).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from functools import lru_cache
from typing import Any


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _pem_from_env(value_key: str, path_key: str) -> bytes | None:
    pem = os.environ.get(value_key, "").strip()
    if pem:
        normalized = pem.replace("\\n", "\n").encode("utf-8")
        # Common misconfig: pasting a JWKS URL into the private-key field.
        text = normalized.decode("utf-8", errors="replace").lstrip()
        if text.startswith(("http://", "https://")) or ".well-known/jwks" in text:
            return None
        if "BEGIN" not in text or "PRIVATE KEY" not in text:
            return None
        return normalized
    path = os.environ.get(path_key, "").strip()
    if path and os.path.isfile(path):
        with open(path, "rb") as handle:
            return handle.read()
    return None


def load_private_pem(*, environment: str = "production") -> bytes | None:
    """Load the RSA private key used for JWT client assertions.

    Prefer non-production keys when environment="nonprod" (Epic sandbox).
    Falls back to production keys if nonprod keys are unset.
    """
    env = (environment or "production").strip().lower()
    if env in {"nonprod", "non-production", "sandbox"}:
        pem = _pem_from_env(
            "PORTAL_NONPROD_JWT_PRIVATE_KEY",
            "PORTAL_NONPROD_JWT_PRIVATE_KEY_PATH",
        )
        if pem:
            return pem
    return _pem_from_env("PORTAL_JWT_PRIVATE_KEY", "PORTAL_JWT_PRIVATE_KEY_PATH")


def signing_algorithm(*, environment: str = "production") -> str:
    env = (environment or "production").strip().lower()
    if env in {"nonprod", "non-production", "sandbox"}:
        nonprod = os.environ.get("PORTAL_NONPROD_JWT_ALG", "").strip()
        if nonprod:
            return nonprod.upper()
    return os.environ.get("PORTAL_JWT_ALG", "RS384").strip().upper() or "RS384"


def signing_kid(
    jwks: dict[str, Any] | None = None, *, environment: str = "production"
) -> str | None:
    env = (environment or "production").strip().lower()
    if env in {"nonprod", "non-production", "sandbox"}:
        explicit = os.environ.get("PORTAL_NONPROD_JWT_KID", "").strip()
        if explicit:
            return explicit
    else:
        explicit = os.environ.get("PORTAL_JWT_KID", "").strip()
        if explicit:
            return explicit
    keys = (jwks or get_jwks(environment=environment)).get("keys") or []
    if keys and isinstance(keys[0], dict):
        kid = keys[0].get("kid")
        return str(kid) if kid else None
    return None


def _public_jwk_from_private_pem(
    pem: bytes, *, kid: str | None = None, algorithm: str | None = None
) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("JWT private key must be an RSA private key PEM.")

    public_numbers = private_key.public_key().public_numbers()
    n = _b64url_uint(public_numbers.n)
    e = _b64url_uint(public_numbers.e)
    resolved_kid = kid or hashlib.sha256(f"{n}.{e}".encode("ascii")).hexdigest()[:16]
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": (algorithm or "RS384").strip().upper() or "RS384",
        "kid": resolved_kid,
        "n": n,
        "e": e,
    }


def _parse_jwks_json(raw: str, label: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict) or "keys" not in data:
        raise ValueError(f"{label} must be a JWKS object with a 'keys' array.")
    return data


def build_jwks(*, environment: str = "production") -> dict[str, Any]:
    """Return the public JWK Set for production or non-production."""
    env = (environment or "production").strip().lower()
    if env in {"nonprod", "non-production", "sandbox"}:
        raw = os.environ.get("PORTAL_NONPROD_JWKS_JSON", "").strip()
        if raw:
            return _parse_jwks_json(raw, "PORTAL_NONPROD_JWKS_JSON")
        pem = _pem_from_env(
            "PORTAL_NONPROD_JWT_PRIVATE_KEY",
            "PORTAL_NONPROD_JWT_PRIVATE_KEY_PATH",
        )
        if pem:
            return {
                "keys": [
                    _public_jwk_from_private_pem(
                        pem,
                        kid=os.environ.get("PORTAL_NONPROD_JWT_KID", "").strip() or None,
                        algorithm=signing_algorithm(environment="nonprod"),
                    )
                ]
            }
        # Distinct URL can temporarily reuse production key material.
        return build_jwks(environment="production")

    raw = os.environ.get("PORTAL_JWKS_JSON", "").strip()
    if raw:
        return _parse_jwks_json(raw, "PORTAL_JWKS_JSON")

    pem = load_private_pem(environment="production")
    if pem is None:
        return {"keys": []}

    return {
        "keys": [
            _public_jwk_from_private_pem(
                pem,
                kid=os.environ.get("PORTAL_JWT_KID", "").strip() or None,
                algorithm=signing_algorithm(environment="production"),
            )
        ]
    }


@lru_cache(maxsize=2)
def get_jwks(environment: str = "production") -> dict[str, Any]:
    """Cached JWKS for request serving. Clear cache after env changes in tests."""
    return build_jwks(environment=environment)


def clear_jwks_cache() -> None:
    get_jwks.cache_clear()


def jwks_is_configured(*, environment: str = "production") -> bool:
    return bool(get_jwks(environment=environment).get("keys"))


def public_jwks_uri(
    preferred_base: str | None = None, *, environment: str = "production"
) -> str | None:
    """Absolute JWKS URI for vendor registration and dashboard display."""
    env = (environment or "production").strip().lower()
    if env in {"nonprod", "non-production", "sandbox"}:
        explicit = os.environ.get("PORTAL_NONPROD_JWKS_URI", "").strip()
        if explicit:
            return explicit.rstrip("/")
        base = (preferred_base or os.environ.get("PUBLIC_BASE_URL", "")).strip().rstrip("/")
        if not base:
            return None
        return f"{base}/.well-known/jwks-nonprod.json"

    explicit = os.environ.get("PORTAL_JWKS_URI", "").strip()
    if explicit:
        return explicit.rstrip("/")

    base = (preferred_base or os.environ.get("PUBLIC_BASE_URL", "")).strip().rstrip("/")
    if not base:
        return None
    return f"{base}/.well-known/jwks.json"


def active_jwt_environment() -> str:
    """Which key set to use for token signing (sandbox defaults to nonprod)."""
    explicit = os.environ.get("FHIR_JWT_ENVIRONMENT", "").strip().lower()
    if explicit in {"nonprod", "non-production", "sandbox", "production", "prod"}:
        if explicit in {"prod", "production"}:
            return "production"
        if explicit in {"non-production", "sandbox"}:
            return "nonprod"
        return explicit
    # Epic sandbox testing: prefer nonprod keys when configured.
    if os.environ.get("PORTAL_NONPROD_JWT_PRIVATE_KEY", "").strip() or os.environ.get(
        "PORTAL_NONPROD_JWT_PRIVATE_KEY_PATH", ""
    ).strip():
        return "nonprod"
    return "production"
