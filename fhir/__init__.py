"""FHIR vendor integration scaffolding for the Patient/Advocate Portal."""

from fhir.client import (
    EPIC_SANDBOX_TEST_PATIENT_ID,
    FHIRClient,
    get_fhir_client,
    normalize_portal_environment,
)
from fhir.jwks import get_jwks, jwks_is_configured, public_jwks_uri

__all__ = [
    "EPIC_SANDBOX_TEST_PATIENT_ID",
    "FHIRClient",
    "get_fhir_client",
    "get_jwks",
    "jwks_is_configured",
    "normalize_portal_environment",
    "public_jwks_uri",
]
