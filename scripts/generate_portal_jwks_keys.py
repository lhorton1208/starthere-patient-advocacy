#!/usr/bin/env python3
"""Generate an RSA key pair and public JWKS for the StartHere Portal.

Usage:
  python scripts/generate_portal_jwks_keys.py

Prints env values to paste into .env / Render secrets. Keep the private key
secret; register PORTAL_JWKS_URI (https://<host>/.well-known/jwks.json) with
the FHIR vendor.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def main() -> int:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    public_numbers = private_key.public_key().public_numbers()
    n = _b64url_uint(public_numbers.n)
    e = _b64url_uint(public_numbers.e)
    kid = secrets.token_hex(8)
    alg = "RS384"
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": alg,
        "kid": kid,
        "n": n,
        "e": e,
    }
    jwks = {"keys": [jwk]}

    # Escape newlines for single-line env vars
    private_env = private_pem.replace("\n", "\\n")
    jwks_env = json.dumps(jwks, separators=(",", ":"))

    print("# StartHere Portal JWKS — paste into .env / hosting secrets")
    print(f"PORTAL_JWT_KID={kid}")
    print(f"PORTAL_JWT_ALG={alg}")
    print(f"PORTAL_JWT_PRIVATE_KEY={private_env}")
    print(f"PORTAL_JWKS_JSON={jwks_env}")
    print("# Set PUBLIC_BASE_URL to your production origin, or override:")
    print("# PORTAL_JWKS_URI=https://your-domain.example/.well-known/jwks.json")
    print()
    print("# Public JWKS (also served at /.well-known/jwks.json once configured):")
    print(json.dumps(jwks, indent=2))
    print()
    print(
        f"# thumbprint hint: {hashlib.sha256(f'{n}.{e}'.encode()).hexdigest()[:16]}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
