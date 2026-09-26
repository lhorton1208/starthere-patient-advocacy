"""OAuth2 helpers for SMART Backend Services and patient App Launch.

Supports:
  - private_key_jwt (Epic Backend OAuth 2.0 / SMART Backend Services)
  - client_secret_basic (generic confidential clients)
  - authorization_code + PKCE (patient MyChart / SMART App Launch)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from fhir.jwt_assert import create_client_assertion


@dataclass
class TokenResponse:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    scope: str | None = None
    patient: str | None = None
    raw: dict | None = None


@dataclass
class PkcePair:
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


def generate_pkce_pair() -> PkcePair:
    """Create a PKCE verifier/challenge pair (S256) for authorization_code flows."""
    # 64 url-safe bytes → ~86 chars; within the 43–128 range Epic expects.
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(code_verifier=verifier, code_challenge=challenge)


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorize_url(
    *,
    authorize_url: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    aud: str | None = None,
) -> str:
    """Build a SMART App Launch / OAuth2 authorize URL (patient signs in at Epic)."""
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }
    if aud:
        params["aud"] = aud
    return f"{authorize_url.rstrip('/')}?{urllib.parse.urlencode(params)}"


def _post_token(token_url: str, body: dict[str, str], *, headers: dict[str, str], timeout: float) -> TokenResponse:
    data = urllib.parse.urlencode(body).encode("utf-8")
    request = urllib.request.Request(token_url, data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Token request failed ({exc.code}): {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Token request failed: {exc.reason}") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Token response did not include access_token.")

    patient = payload.get("patient")
    if patient is not None:
        patient = str(patient)

    return TokenResponse(
        access_token=access_token,
        token_type=payload.get("token_type", "Bearer"),
        expires_in=payload.get("expires_in"),
        scope=payload.get("scope"),
        patient=patient,
        raw=payload,
    )


def request_client_credentials_token(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str | None = None,
    timeout: float = 30.0,
) -> TokenResponse:
    """POST grant_type=client_credentials using HTTP Basic client authentication."""
    body: dict[str, str] = {"grant_type": "client_credentials"}
    if scope:
        body["scope"] = scope

    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    return _post_token(
        token_url,
        body,
        headers={
            "Authorization": "Basic " + base64.b64encode(credentials).decode("ascii"),
        },
        timeout=timeout,
    )


def request_private_key_jwt_token(
    *,
    token_url: str,
    client_id: str,
    private_key_pem: bytes,
    scope: str | None = None,
    algorithm: str = "RS384",
    kid: str | None = None,
    jku: str | None = None,
    timeout: float = 30.0,
) -> TokenResponse:
    """POST grant_type=client_credentials with JWT client_assertion (Epic-compatible)."""
    assertion = create_client_assertion(
        client_id=client_id,
        token_url=token_url,
        private_key_pem=private_key_pem,
        algorithm=algorithm,
        kid=kid,
        jku=jku,
    )
    body: dict[str, str] = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
    }
    if scope:
        body["scope"] = scope

    return _post_token(token_url, body, headers={}, timeout=timeout)


def request_authorization_code_token(
    *,
    token_url: str,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_secret: str | None = None,
    private_key_pem: bytes | None = None,
    algorithm: str = "RS384",
    kid: str | None = None,
    jku: str | None = None,
    timeout: float = 30.0,
) -> TokenResponse:
    """Exchange an authorization code for a patient access token (PKCE).

    Prefers private_key_jwt client authentication when a PEM is provided;
    otherwise uses client_secret_basic when a secret is provided; otherwise
    sends client_id in the body (public / PKCE-only clients).
    """
    body: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    headers: dict[str, str] = {}

    if private_key_pem:
        assertion = create_client_assertion(
            client_id=client_id,
            token_url=token_url,
            private_key_pem=private_key_pem,
            algorithm=algorithm,
            kid=kid,
            jku=jku,
        )
        body["client_id"] = client_id
        body["client_assertion_type"] = (
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        )
        body["client_assertion"] = assertion
    elif client_secret:
        credentials = f"{client_id}:{client_secret}".encode("utf-8")
        headers["Authorization"] = (
            "Basic " + base64.b64encode(credentials).decode("ascii")
        )
    else:
        body["client_id"] = client_id

    return _post_token(token_url, body, headers=headers, timeout=timeout)


def client_secret_configured() -> bool:
    return bool(
        os.environ.get("FHIR_TOKEN_URL", "").strip()
        and os.environ.get("FHIR_CLIENT_ID", "").strip()
        and os.environ.get("FHIR_CLIENT_SECRET", "").strip()
    )


def private_key_jwt_configured() -> bool:
    from fhir.jwks import active_jwt_environment, load_private_pem

    return bool(
        os.environ.get("FHIR_TOKEN_URL", "").strip()
        and os.environ.get("FHIR_CLIENT_ID", "").strip()
        and load_private_pem(environment=active_jwt_environment())
    )


def credentials_configured() -> bool:
    """True when either JWT assertion or client-secret credentials are present."""
    return private_key_jwt_configured() or client_secret_configured()
