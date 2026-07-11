"""OAuth2 client_credentials helper for SMART Backend Services (client secret)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass
class TokenResponse:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    scope: str | None = None
    raw: dict | None = None


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

    data = urllib.parse.urlencode(body).encode("utf-8")
    request = urllib.request.Request(token_url, data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")

    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    import base64

    request.add_header(
        "Authorization",
        "Basic " + base64.b64encode(credentials).decode("ascii"),
    )

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

    return TokenResponse(
        access_token=access_token,
        token_type=payload.get("token_type", "Bearer"),
        expires_in=payload.get("expires_in"),
        scope=payload.get("scope"),
        raw=payload,
    )


def credentials_configured() -> bool:
    return bool(
        os.environ.get("FHIR_TOKEN_URL", "").strip()
        and os.environ.get("FHIR_CLIENT_ID", "").strip()
        and os.environ.get("FHIR_CLIENT_SECRET", "").strip()
    )
