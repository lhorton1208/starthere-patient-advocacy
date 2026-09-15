"""FHIR client interface, demo data, and live Epic-compatible backend client.

Live backend-services auth prefers private_key_jwt (Epic Backend OAuth 2.0),
with client_secret_basic as a fallback. Register PORTAL_JWKS_URI
(/.well-known/jwks.json) as the app's JWK Set URL on fhir.epic.com.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from fhir.http import build_search_url, fhir_request
from fhir.jwks import (
    active_jwt_environment,
    jwks_is_configured,
    load_private_pem,
    public_jwks_uri,
    signing_algorithm,
    signing_kid,
)
from fhir.mapping import (
    map_coverage,
    map_encounters,
    map_observations,
    map_procedures,
    patient_display_name,
)
from fhir.models import (
    ConnectionStatus,
    EncounterItem,
    InsuranceApproval,
    PortalDashboard,
    ProcedureItem,
    TestResult,
)
from fhir.oauth import (
    request_client_credentials_token,
    request_private_key_jwt_token,
)


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
                "FHIR_TOKEN_URL, FHIR_CLIENT_ID, and PORTAL_JWT_PRIVATE_KEY for "
                "Epic Backend OAuth (private_key_jwt), or FHIR_CLIENT_SECRET for "
                "client_secret_basic."
                + jwks_note
            ),
            base_url=None,
            jwks_uri=jwks_uri,
            auth_method="private_key_jwt",
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
    """FHIR R4 client using SMART Backend Services against Epic (or similar)."""

    def __init__(
        self,
        base_url: str,
        *,
        token_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
        access_token: str | None = None,
        default_patient_id: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token_url = (token_url or "").rstrip("/") or None
        self.client_id = client_id or None
        self.client_secret = client_secret or None
        self.scope = scope or None
        self._static_access_token = access_token
        self._cached_access_token: str | None = None
        self._auth_method: str | None = None
        self._last_auth_error: str | None = None
        self._last_fetch_notes: list[str] = []
        self.default_patient_id = default_patient_id or None

    def _jwt_ready(self) -> bool:
        env = active_jwt_environment()
        return bool(self.token_url and self.client_id and load_private_pem(environment=env))

    def _secret_ready(self) -> bool:
        return bool(self.token_url and self.client_id and self.client_secret)

    def _obtain_access_token(self) -> str | None:
        self._last_auth_error = None
        if self._static_access_token:
            self._auth_method = "static_token"
            return self._static_access_token
        if self._cached_access_token:
            return self._cached_access_token

        jwt_env = active_jwt_environment()
        if self._jwt_ready():
            pem = load_private_pem(environment=jwt_env)
            assert pem is not None and self.token_url and self.client_id
            token = request_private_key_jwt_token(
                token_url=self.token_url,
                client_id=self.client_id,
                private_key_pem=pem,
                scope=self.scope,
                algorithm=signing_algorithm(environment=jwt_env),
                kid=signing_kid(environment=jwt_env),
                jku=public_jwks_uri(environment=jwt_env),
            )
            self._cached_access_token = token.access_token
            self._auth_method = "private_key_jwt"
            return self._cached_access_token

        if self._secret_ready():
            assert self.token_url and self.client_id and self.client_secret
            token = request_client_credentials_token(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
            )
            self._cached_access_token = token.access_token
            self._auth_method = "client_secret"
            return self._cached_access_token

        return None

    def get_connection_status(self) -> ConnectionStatus:
        jwt_env = active_jwt_environment()
        jwks_uri = public_jwks_uri(environment=jwt_env)
        has_static = bool(self._static_access_token)
        jwt_ready = self._jwt_ready()
        secret_ready = self._secret_ready()
        jwks_ready = jwks_is_configured(environment=jwt_env)

        if not (has_static or jwt_ready or secret_ready):
            detail = (
                "Set FHIR_TOKEN_URL, FHIR_CLIENT_ID, and PORTAL_JWT_PRIVATE_KEY "
                "for Epic private_key_jwt (preferred), or FHIR_CLIENT_SECRET for "
                "client_secret_basic. Optionally set FHIR_ACCESS_TOKEN to skip "
                "token exchange."
            )
            if not jwks_ready:
                detail += (
                    " Also publish PORTAL_JWKS_JSON (or PORTAL_JWT_PRIVATE_KEY) so "
                    "/.well-known/jwks.json can be registered as the JWK Set URL."
                )
            return ConnectionStatus(
                mode="unconfigured",
                label="Endpoint configured — credentials missing",
                detail=detail,
                base_url=self.base_url,
                jwks_uri=jwks_uri,
                auth_method="private_key_jwt" if not secret_ready else "client_secret",
                grant_type="client_credentials",
            )

        auth_label = self._auth_method or (
            "private_key_jwt"
            if jwt_ready
            else ("static_token" if has_static else "client_secret")
        )
        detail = (
            f"FHIR base {self.base_url} with client_credentials / {auth_label}."
        )
        if self._last_auth_error:
            detail = f"Auth error: {self._last_auth_error}"
        elif self._last_fetch_notes:
            detail += " " + " ".join(self._last_fetch_notes)
        if not jwks_ready and auth_label == "private_key_jwt":
            detail += (
                " JWKS is not published yet — generate keys and register "
                "/.well-known/jwks.json with Epic as the JWK Set URL."
            )
        elif jwks_uri:
            detail += f" JWKS URI: {jwks_uri}."

        mode = "unconfigured" if self._last_auth_error else "live"
        label = (
            "Auth failed"
            if self._last_auth_error
            else "Connected (backend services)"
        )
        return ConnectionStatus(
            mode=mode,
            label=label,
            detail=detail,
            base_url=self.base_url,
            jwks_uri=jwks_uri,
            auth_method=auth_label,
            grant_type="client_credentials",
        )

    def _safe_get(self, path_or_url: str, access_token: str) -> dict | None:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self.base_url}/{path_or_url.lstrip('/')}"
        )
        try:
            return fhir_request("GET", url, access_token=access_token)
        except RuntimeError as exc:
            self._last_fetch_notes.append(str(exc))
            return None

    def fetch_dashboard(self, patient_id: str | None = None) -> PortalDashboard:
        self._last_fetch_notes = []
        resolved_patient_id = (
            (patient_id or "").strip()
            or (self.default_patient_id or "").strip()
            or None
        )

        try:
            access_token = self._obtain_access_token()
        except RuntimeError as exc:
            self._last_auth_error = str(exc)
            access_token = None

        connection = self.get_connection_status()
        if not access_token:
            return PortalDashboard(
                connection=connection,
                patient_display_name=resolved_patient_id or "No patient selected",
            )

        if not resolved_patient_id:
            self._last_fetch_notes.append(
                "Pass ?patient_id=… or set FHIR_PATIENT_ID to pull live chart data "
                "(Epic sandbox example: erXuFYUfucBZaryVksYEcMg3)."
            )
            return PortalDashboard(
                connection=self.get_connection_status(),
                patient_display_name="No patient selected",
            )

        patient = self._safe_get(f"Patient/{resolved_patient_id}", access_token)
        observations = self._safe_get(
            build_search_url(
                self.base_url,
                "Observation",
                {"patient": resolved_patient_id, "category": "laboratory"},
            ),
            access_token,
        )
        encounters = self._safe_get(
            build_search_url(
                self.base_url,
                "Encounter",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )
        coverage = self._safe_get(
            build_search_url(
                self.base_url,
                "Coverage",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )
        procedures = self._safe_get(
            build_search_url(
                self.base_url,
                "Procedure",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )

        if patient:
            self._last_fetch_notes.insert(
                0, f"Live Patient/{resolved_patient_id} loaded."
            )
        else:
            self._last_fetch_notes.insert(
                0, f"Could not load Patient/{resolved_patient_id}."
            )

        return PortalDashboard(
            connection=self.get_connection_status(),
            patient_display_name=patient_display_name(patient)
            if patient
            else resolved_patient_id,
            test_results=map_observations(observations),
            insurance_approvals=map_coverage(coverage),
            procedures=map_procedures(procedures),
            encounters=map_encounters(encounters),
        )


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
            default_patient_id=os.environ.get("FHIR_PATIENT_ID", "").strip() or None,
        )
    return DemoFHIRClient()
