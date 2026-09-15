"""Build one-time client_assertion JWTs for SMART Backend Services (Epic)."""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_ALG_HASH = {
    "RS256": hashes.SHA256(),
    "RS384": hashes.SHA384(),
    "RS512": hashes.SHA512(),
}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _compact_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=False).encode("utf-8")


def create_client_assertion(
    *,
    client_id: str,
    token_url: str,
    private_key_pem: bytes,
    algorithm: str = "RS384",
    kid: str | None = None,
    jku: str | None = None,
    lifetime_seconds: int = 240,
) -> str:
    """Create a signed JWT for grant_type=client_credentials client_assertion.

    Epic requires exp/iat/nbf windows of at most 5 minutes. Default lifetime is
    4 minutes to leave clock-skew margin.
    """
    alg = (algorithm or "RS384").strip().upper()
    hash_alg = _ALG_HASH.get(alg)
    if hash_alg is None:
        raise ValueError(f"Unsupported JWT algorithm for RSA assertion: {alg}")

    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("Client assertion private key must be RSA PEM.")

    now = int(time.time())
    lifetime = max(30, min(int(lifetime_seconds), 300))
    header: dict[str, Any] = {"alg": alg, "typ": "JWT"}
    if kid:
        header["kid"] = kid
    if jku:
        header["jku"] = jku

    claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_url,
        "jti": str(uuid.uuid4()),
        "exp": now + lifetime,
        "nbf": now,
        "iat": now,
    }

    signing_input = f"{_b64url(_compact_json(header))}.{_b64url(_compact_json(claims))}"
    signature = private_key.sign(
        signing_input.encode("ascii"),
        padding.PKCS1v15(),
        hash_alg,
    )
    return f"{signing_input}.{_b64url(signature)}"
