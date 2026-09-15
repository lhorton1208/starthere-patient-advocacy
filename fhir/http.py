"""Minimal FHIR R4 HTTP helpers (urllib, no extra deps)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def fhir_request(
    method: str,
    url: str,
    *,
    access_token: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Perform an authenticated FHIR request and return parsed JSON."""
    request = urllib.request.Request(url, method=method.upper())
    request.add_header("Authorization", f"Bearer {access_token}")
    request.add_header("Accept", "application/fhir+json, application/json")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"FHIR {method.upper()} {url} failed ({exc.code}): {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"FHIR {method.upper()} {url} failed: {exc.reason}") from exc

    if not body.strip():
        return {}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"FHIR response was not JSON from {url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"FHIR response was not a JSON object from {url}")
    return payload


def build_search_url(base_url: str, resource_type: str, params: dict[str, str]) -> str:
    root = base_url.rstrip("/")
    query = urllib.parse.urlencode(params)
    return f"{root}/{resource_type}?{query}"
