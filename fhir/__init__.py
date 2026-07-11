"""FHIR vendor integration scaffolding for the Patient/Advocate Portal."""

from fhir.client import FHIRClient, get_fhir_client
from fhir.jwks import get_jwks, jwks_is_configured, public_jwks_uri

__all__ = [
    "FHIRClient",
    "get_fhir_client",
    "get_jwks",
    "jwks_is_configured",
    "public_jwks_uri",
]
