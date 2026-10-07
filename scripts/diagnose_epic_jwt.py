#!/usr/bin/env python3
"""Diagnose Epic Backend Services private_key_jwt setup (sandbox).

Loads env the same way the app does, compares the local private key to the
live JWKS URL, then attempts a sandbox token request.

Usage (after exporting Render env locally, or with a filled .env):

  set -a && source .env && set +a
  ./venv/bin/python scripts/diagnose_epic_jwt.py

Never paste PORTAL_JWT_PRIVATE_KEY output into chat.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fhir.client import normalize_portal_environment, resolve_fhir_connection_settings
from fhir.jwks import (
    _b64url_uint,
    load_private_pem,
    public_jwks_uri,
    signing_algorithm,
    signing_kid,
)
from fhir.oauth import request_private_key_jwt_token


def _load_dotenv() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, value = raw.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _fetch_jwks(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _public_from_pem(pem: bytes) -> tuple[str, str]:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("Not an RSA private key")
    numbers = key.public_key().public_numbers()
    return _b64url_uint(numbers.n), _b64url_uint(numbers.e)


def main() -> int:
    _load_dotenv()
    environment = normalize_portal_environment(
        sys.argv[1] if len(sys.argv) > 1 else "sandbox"
    )
    settings = resolve_fhir_connection_settings(environment)
    jwt_env = settings["jwt_environment"] or "nonprod"
    client_id = settings["client_id"]
    token_url = settings["token_url"]
    scope = settings["scope"]
    pem = load_private_pem(environment=jwt_env)
    alg = signing_algorithm(environment=jwt_env)
    kid = signing_kid(environment=jwt_env)
    jku = public_jwks_uri(environment=jwt_env)

    print(f"portal_environment={environment}")
    print(f"jwt_environment={jwt_env}")
    print(f"client_id={client_id}")
    print(f"token_url={token_url}")
    print(f"alg={alg}")
    print(f"kid(header)={kid}")
    print(f"jku={jku}")
    print(f"private_key_present={bool(pem)}")

    if not pem:
        print("FAIL: no private key loaded for this environment.")
        print(
            "Set PORTAL_NONPROD_JWT_PRIVATE_KEY (sandbox) or "
            "PORTAL_JWT_PRIVATE_KEY (production)."
        )
        return 1
    if not client_id or not token_url:
        print("FAIL: missing FHIR client id or token URL.")
        return 1
    if not jku:
        print("FAIL: could not resolve JWKS URI.")
        return 1

    try:
        pem_n, pem_e = _public_from_pem(pem)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: private key is not a usable RSA PEM ({exc}).")
        return 1

    try:
        jwks = _fetch_jwks(jku)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not fetch JWKS from {jku}: {exc}")
        return 1

    keys = jwks.get("keys") or []
    if not keys:
        print("FAIL: JWKS has no keys.")
        return 1

    match = None
    for key in keys:
        if key.get("n") == pem_n and key.get("e") == pem_e:
            match = key
            break

    print(f"jwks_key_count={len(keys)}")
    print(f"jwks_kids={[k.get('kid') for k in keys]}")
    print(f"jwks_algs={[k.get('alg') for k in keys]}")
    if match is None:
        print("FAIL: private key does NOT match any public key in the live JWKS.")
        print(
            "Fix: regenerate with scripts/generate_portal_jwks_keys.py and update "
            "BOTH the private key and JWKS JSON/kid on Render together, then redeploy."
        )
        return 2

    print(f"key_match=OK kid={match.get('kid')} alg={match.get('alg')}")
    if kid and match.get("kid") and kid != match.get("kid"):
        print(
            f"FAIL: JWT kid header ({kid}) != JWKS kid ({match.get('kid')}). "
            "Clear the stale PORTAL_*_JWT_KID or set it to the JWKS kid."
        )
        return 3
    if match.get("alg") and alg and match.get("alg").upper() != alg.upper():
        print(
            f"WARN: JWT alg ({alg}) != JWKS alg ({match.get('alg')}). "
            "Set PORTAL_JWT_ALG / PORTAL_NONPROD_JWT_ALG to match JWKS (usually RS384)."
        )

    try:
        token = request_private_key_jwt_token(
            token_url=token_url,
            client_id=client_id,
            private_key_pem=pem,
            scope=scope,
            algorithm=alg,
            kid=kid or match.get("kid"),
            jku=jku,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: token request error: {exc}")
        print(
            "If key_match=OK but Epic still returns invalid_client, check Epic app:\n"
            "  - Non-Production JWK Set URL is exactly this jku (www host)\n"
            "  - Non-Production Client ID matches client_id above\n"
            "  - App audience is Backend Systems\n"
            "  - Wait a few minutes after JWKS changes for Epic cache"
        )
        return 4

    print(f"SUCCESS: got access token (len={len(token.access_token)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
