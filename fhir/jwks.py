"""JWKS helpers for the StartHere Patient/Advocate Portal.

Publishes the public key set at /.well-known/jwks.json for vendor registration
(jwks_uri). Token auth for backend services uses client_secret + client_credentials;
the private key is kept available for future private_key_jwt if a vendor requires it.
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


def _load_private_pem() -> bytes | None:
    pem = os.environ.get("PORTAL_JWT_PRIVATE_KEY", "").strip()
    if pem:
        return pem.replace("\\n", "\n").encode("utf-8")
    path = os.environ.get("PORTAL_JWT_PRIVATE_KEY_PATH", "").strip()
    if path and os.path.isfile(path):
        with open(path, "rb") as handle:
            return handle.read()
    return None


def _public_jwk_from_private_pem(pem: bytes, kid: str | None = None) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("PORTAL_JWT_PRIVATE_KEY must be an RSA private key PEM.")

    public_numbers = private_key.public_key().public_numbers()
    n = _b64url_uint(public_numbers.n)
    e = _b64url_uint(public_numbers.e)
    resolved_kid = kid or os.environ.get("PORTAL_JWT_KID", "").strip()
    if not resolved_kid:
        resolved_kid = hashlib.sha256(f"{n}.{e}".encode("ascii")).hexdigest()[:16]

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": os.environ.get("PORTAL_JWT_ALG", "RS384").strip() or "RS384",
        "kid": resolved_kid,
        "n": n,
        "e": e,
    }


def build_jwks() -> dict[str, Any]:
    """Return the public JWK Set to serve at the JWKS URI."""
    raw = os.environ.get("PORTAL_JWKS_JSON", "").strip()
    if raw:
        data = json.loads(raw)
        if not isinstance(data, dict) or "keys" not in data:
            raise ValueError("PORTAL_JWKS_JSON must be a JWKS object with a 'keys' array.")
        return data

    pem = _load_private_pem()
    if pem is None:
        return {"keys": []}

    return {"keys": [_public_jwk_from_private_pem(pem)]}


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """Cached JWKS for request serving. Clear cache after env changes in tests."""
    return build_jwks()


def clear_jwks_cache() -> None:
    get_jwks.cache_clear()


def jwks_is_configured() -> bool:
    return bool(get_jwks().get("keys"))


def public_jwks_uri(preferred_base: str | None = None) -> str | None:
    """Absolute JWKS URI for vendor registration and dashboard display."""
    explicit = os.environ.get("PORTAL_JWKS_URI", "").strip()
    if explicit:
        return explicit.rstrip("/")

    base = (preferred_base or os.environ.get("PUBLIC_BASE_URL", "")).strip().rstrip("/")
    if not base:
        return None
    return f"{base}/.well-known/jwks.json"
