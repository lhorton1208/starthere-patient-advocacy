"""FHIR client interface and demo implementation.

Live backend-services auth uses OAuth2 client_credentials with a client secret.
Register PORTAL_JWKS_URI (/.well-known/jwks.json) with the vendor as requested.
Keep mapping logic in `_map_*` helpers so the dashboard contract stays unchanged.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from fhir.jwks import jwks_is_configured, public_jwks_uri
from fhir.models import (
    ConnectionStatus,
    EncounterItem,
    InsuranceApproval,
    PortalDashboard,
    ProcedureItem,
    TestResult,
)
from fhir.oauth import request_client_credentials_token


class FHIRClient(ABC):
    """Vendor-agnostic FHIR access used by the portal dashboard."""

    @abstractmethod
    def get_connection_status(self) -> ConnectionStatus:
        raise NotImplementedError

    @abstractmethod
    def fetch_dashboard(self, patient_id: str | None = None) -> PortalDashboard:
        """Query FHIR endpoints and return normalized dashboard data.

        Expected resource families (R4):
          - Observation / DiagnosticReport  → test results
          - ClaimResponse / Coverage        → insurance approvals
          - ServiceRequest / Procedure      → procedures ordered/completed
          - Encounter                       → encounters scheduled/completed
        """
        raise NotImplementedError


class DemoFHIRClient(FHIRClient):
    """Returns sample data shaped like live FHIR mappings for UI scaffolding."""

    def get_connection_status(self) -> ConnectionStatus:
        jwks_uri = public_jwks_uri()
        jwks_note = (
            f" JWKS URI for vendor registration: {jwks_uri}."
            if jwks_uri and jwks_is_configured()
            else (
                " Generate portal keys (scripts/generate_portal_jwks_keys.py) and "
                "set PUBLIC_BASE_URL so /.well-known/jwks.json can be registered."
                if not jwks_is_configured()
                else " Set PUBLIC_BASE_URL or PORTAL_JWKS_URI for the absolute JWKS URL."
            )
        )
        return ConnectionStatus(
            mode="demo",
            label="Demo mode",
            detail=(
                "Showing sample FHIR-shaped data. Configure FHIR_BASE_URL, "
                "FHIR_TOKEN_URL, FHIR_CLIENT_ID, and FHIR_CLIENT_SECRET for "
                "backend services (client_credentials)."
                + jwks_note
            ),
            base_url=None,
            jwks_uri=jwks_uri,
            auth_method="client_secret",
            grant_type="client_credentials",
        )

    def fetch_dashboard(self, patient_id: str | None = None) -> PortalDashboard:
        _ = patient_id  # Reserved for Patient/{id} queries once auth is wired
        return PortalDashboard(
            connection=self.get_connection_status(),
            patient_display_name="Sample Patient",
            test_results=[
                TestResult(
                    id="obs-1001",
                    name="Comprehensive Metabolic Panel",
                    status="final",
                    result_summary="Within normal limits",
                    effective_date="2026-06-28",
                    ordered_by="Dr. Rivera",
                    category="Laboratory",
                ),
                TestResult(
                    id="obs-1002",
                    name="CBC with Differential",
                    status="preliminary",
                    result_summary="Pending pathologist review",
                    effective_date="2026-07-02",
                    ordered_by="Dr. Rivera",
                    category="Laboratory",
                ),
                TestResult(
                    id="dr-2001",
                    name="Chest X-Ray (2 views)",
                    status="final",
                    result_summary="No acute cardiopulmonary process",
                    effective_date="2026-06-15",
                    ordered_by="Dr. Patel",
                    category="Imaging",
                ),
            ],
            insurance_approvals=[
                InsuranceApproval(
                    id="auth-501",
                    service_name="MRI Lumbar Spine without contrast",
                    status="approved",
                    payer="Blue Cross Blue Shield NC",
                    decision_date="2026-06-20",
                    authorization_number="AUTH-88421",
                    notes="Valid through 2026-09-20",
                ),
                InsuranceApproval(
                    id="auth-502",
                    service_name="Outpatient physical therapy (12 visits)",
                    status="pending",
                    payer="Blue Cross Blue Shield NC",
                    decision_date="2026-07-01",
                    notes="Additional clinical notes requested",
                ),
            ],
            procedures=[
                ProcedureItem(
                    id="sr-301",
                    name="Colonoscopy",
                    status="ordered",
                    scheduled_or_performed="2026-07-18",
                    location="Triangle Endoscopy Center",
                    performer="Dr. Chen",
                ),
                ProcedureItem(
                    id="proc-302",
                    name="Knee arthroscopy (right)",
                    status="completed",
                    scheduled_or_performed="2026-05-12",
                    location="Rex Hospital",
                    performer="Dr. Alvarez",
                ),
            ],
            encounters=[
                EncounterItem(
                    id="enc-401",
                    encounter_type="Office visit",
                    status="completed",
                    when="2026-06-10 10:30 AM",
                    location="StartHere Partner Clinic — Raleigh",
                    reason="Medication review",
                    provider="Dr. Rivera",
                ),
                EncounterItem(
                    id="enc-402",
                    encounter_type="Follow-up",
                    status="scheduled",
                    when="2026-07-22 2:00 PM",
                    location="StartHere Partner Clinic — Raleigh",
                    reason="Post-procedure check",
                    provider="Dr. Chen",
                ),
                EncounterItem(
                    id="enc-403",
                    encounter_type="ED visit",
                    status="completed",
                    when="2026-04-03 8:15 PM",
                    location="WakeMed Raleigh",
                    reason="Acute back pain",
                    provider="ED Team",
                ),
            ],
        )


class LiveFHIRClient(FHIRClient):
    """FHIR R4 client using SMART Backend Services (client_credentials + secret).

    Token exchange is implemented. Resource GETs still fall back to demo data
    until Bundle mapping is completed for the vendor's FHIR API.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
        access_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token_url = (token_url or "").rstrip("/") or None
        self.client_id = client_id or None
        self.client_secret = client_secret or None
        self.scope = scope or None
        self._static_access_token = access_token
        self._cached_access_token: str | None = None

    def _obtain_access_token(self) -> str | None:
        if self._static_access_token:
            return self._static_access_token
        if self._cached_access_token:
            return self._cached_access_token
        if not (self.token_url and self.client_id and self.client_secret):
            return None
        token = request_client_credentials_token(
            token_url=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
        )
        self._cached_access_token = token.access_token
        return self._cached_access_token

    def get_connection_status(self) -> ConnectionStatus:
        jwks_uri = public_jwks_uri()
        has_creds = bool(self.token_url and self.client_id and self.client_secret)
        has_static = bool(self._static_access_token)
        jwks_ready = jwks_is_configured()

        if not (has_creds or has_static):
            detail = (
                "Set FHIR_TOKEN_URL, FHIR_CLIENT_ID, and FHIR_CLIENT_SECRET for "
                "client_credentials, or FHIR_ACCESS_TOKEN for a pre-issued token."
            )
            if not jwks_ready:
                detail += (
                    " Also publish PORTAL_JWKS_JSON (or PORTAL_JWT_PRIVATE_KEY) so "
                    "/.well-known/jwks.json can be registered as jwks_uri."
                )
            return ConnectionStatus(
                mode="unconfigured",
                label="Endpoint configured — credentials missing",
                detail=detail,
                base_url=self.base_url,
                jwks_uri=jwks_uri,
                auth_method="client_secret",
                grant_type="client_credentials",
            )

        detail = (
            f"FHIR base {self.base_url} with client_credentials / client_secret. "
            "Dashboard resource queries still use sample data until live Bundle "
            "mapping is enabled."
        )
        if not jwks_ready:
            detail += (
                " JWKS is not published yet — generate keys and register "
                "/.well-known/jwks.json with the vendor."
            )
        elif jwks_uri:
            detail += f" JWKS URI: {jwks_uri}."

        return ConnectionStatus(
            mode="live",
            label="Connected (backend services)",
            detail=detail,
            base_url=self.base_url,
            jwks_uri=jwks_uri,
            auth_method="client_secret",
            grant_type="client_credentials",
        )

    def fetch_dashboard(self, patient_id: str | None = None) -> PortalDashboard:
        # Attempt token acquisition so misconfiguration surfaces early in logs/status.
        try:
            self._obtain_access_token()
        except RuntimeError:
            # Keep demo dashboard usable; connection status reflects config state.
            pass

        demo = DemoFHIRClient().fetch_dashboard(patient_id)
        demo.connection = self.get_connection_status()
        demo.patient_display_name = patient_id or "Connected Patient"
        return demo


def get_fhir_client() -> FHIRClient:
    """Factory: live client when FHIR_BASE_URL is set, otherwise demo."""
    base_url = os.environ.get("FHIR_BASE_URL", "").strip()
    if base_url:
        return LiveFHIRClient(
            base_url=base_url,
            token_url=os.environ.get("FHIR_TOKEN_URL", "").strip() or None,
            client_id=os.environ.get("FHIR_CLIENT_ID", "").strip() or None,
            client_secret=os.environ.get("FHIR_CLIENT_SECRET", "").strip() or None,
            scope=os.environ.get("FHIR_SCOPE", "").strip() or None,
            access_token=os.environ.get("FHIR_ACCESS_TOKEN", "").strip() or None,
        )
    return DemoFHIRClient()
