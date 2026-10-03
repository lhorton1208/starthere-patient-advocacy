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
    map_allergies,
    map_coverage,
    map_diagnoses,
    map_encounters,
    map_medications,
    map_observations,
    map_problems,
    map_procedures,
    map_provider_notes,
    patient_display_name,
)
from fhir.models import (
    AllergyItem,
    ConnectionStatus,
    DiagnosisItem,
    EncounterItem,
    InsuranceApproval,
    MedicationItem,
    PortalDashboard,
    ProblemItem,
    ProcedureItem,
    ProviderNoteItem,
    TestResult,
)
from fhir.oauth import (
    request_client_credentials_token,
    request_private_key_jwt_token,
)

# Well-known Epic open-sandbox FHIR patient used for Backend Services demos.
EPIC_SANDBOX_TEST_PATIENT_ID = "erXuFYUfucBZaryVksYEcMg3"


def normalize_portal_environment(value: str | None) -> str:
    """Return ``sandbox`` or ``production`` for portal EHR targeting."""
    raw = (value or "").strip().lower()
    if raw in {"production", "prod"}:
        return "production"
    if raw in {"nonprod", "non-production", "sandbox", "test"}:
        return "sandbox"
    return "sandbox"


def jwt_environment_for_portal(portal_environment: str) -> str:
    """Map portal sandbox/production choice onto JWKS key environment names."""
    if normalize_portal_environment(portal_environment) == "production":
        return "production"
    return "nonprod"


def resolve_fhir_connection_settings(
    environment: str | None = None,
) -> dict[str, str | None]:
    """Resolve FHIR URLs/credentials for sandbox or production.

    Sandbox prefers ``FHIR_SANDBOX_*`` then falls back to ``FHIR_*``.
    Production prefers ``FHIR_PRODUCTION_*`` then falls back to ``FHIR_*``.
    JWT signing uses nonprod keys for sandbox and production keys for production.
    """
    env = normalize_portal_environment(
        environment
        if environment is not None
        else os.environ.get("FHIR_JWT_ENVIRONMENT", "")
    )
    if env == "production":
        base_url = (
            os.environ.get("FHIR_PRODUCTION_BASE_URL", "").strip()
            or os.environ.get("FHIR_BASE_URL", "").strip()
        )
        token_url = (
            os.environ.get("FHIR_PRODUCTION_TOKEN_URL", "").strip()
            or os.environ.get("FHIR_TOKEN_URL", "").strip()
        )
        client_id = (
            os.environ.get("FHIR_PRODUCTION_CLIENT_ID", "").strip()
            or os.environ.get("FHIR_CLIENT_ID", "").strip()
        )
        client_secret = (
            os.environ.get("FHIR_PRODUCTION_CLIENT_SECRET", "").strip()
            or os.environ.get("FHIR_CLIENT_SECRET", "").strip()
        )
        access_token = (
            os.environ.get("FHIR_PRODUCTION_ACCESS_TOKEN", "").strip()
            or os.environ.get("FHIR_ACCESS_TOKEN", "").strip()
        )
        default_patient_id = os.environ.get(
            "FHIR_PRODUCTION_PATIENT_ID", ""
        ).strip()
    else:
        base_url = (
            os.environ.get("FHIR_SANDBOX_BASE_URL", "").strip()
            or os.environ.get("FHIR_BASE_URL", "").strip()
        )
        token_url = (
            os.environ.get("FHIR_SANDBOX_TOKEN_URL", "").strip()
            or os.environ.get("FHIR_TOKEN_URL", "").strip()
        )
        client_id = (
            os.environ.get("FHIR_SANDBOX_CLIENT_ID", "").strip()
            or os.environ.get("FHIR_CLIENT_ID", "").strip()
        )
        client_secret = (
            os.environ.get("FHIR_SANDBOX_CLIENT_SECRET", "").strip()
            or os.environ.get("FHIR_CLIENT_SECRET", "").strip()
        )
        access_token = os.environ.get("FHIR_ACCESS_TOKEN", "").strip()
        default_patient_id = (
            os.environ.get("FHIR_PATIENT_ID", "").strip()
            or EPIC_SANDBOX_TEST_PATIENT_ID
        )

    return {
        "portal_environment": env,
        "jwt_environment": jwt_environment_for_portal(env),
        "base_url": base_url or None,
        "token_url": token_url or None,
        "client_id": client_id or None,
        "client_secret": client_secret or None,
        "scope": os.environ.get("FHIR_SCOPE", "").strip() or None,
        "access_token": access_token or None,
        "default_patient_id": default_patient_id or None,
    }


class FHIRClient(ABC):
    """Vendor-agnostic FHIR access used by the portal dashboard."""

    @abstractmethod
    def get_connection_status(self) -> ConnectionStatus:
        raise NotImplementedError

    @abstractmethod
    def fetch_dashboard(
        self,
        patient_id: str | None = None,
        *,
        access_token: str | None = None,
        auth_method: str | None = None,
        grant_type: str | None = None,
    ) -> PortalDashboard:
        """Query FHIR endpoints and return normalized dashboard data.

        Expected resource families (R4):
          - Observation / DiagnosticReport  → test results
          - ClaimResponse / Coverage        → insurance approvals
          - ServiceRequest / Procedure      → procedures ordered/completed
          - Encounter                       → encounters scheduled/completed
          - Condition                       → problems / diagnoses
          - MedicationRequest               → medications
          - AllergyIntolerance              → allergies
          - DocumentReference               → provider notes

        Optional `access_token` supplies a patient authorization_code token
        (SMART App Launch) instead of obtaining a backend-services token.
        """
        raise NotImplementedError


class DemoFHIRClient(FHIRClient):
    """Returns sample data shaped like live FHIR mappings for UI scaffolding."""

    def __init__(self, *, portal_environment: str = "sandbox"):
        self.portal_environment = normalize_portal_environment(portal_environment)
        self.jwt_environment = jwt_environment_for_portal(self.portal_environment)

    def get_connection_status(self) -> ConnectionStatus:
        jwks_uri = public_jwks_uri(environment=self.jwt_environment)
        jwks_note = (
            f" JWKS URI for vendor registration: {jwks_uri}."
            if jwks_uri and jwks_is_configured(environment=self.jwt_environment)
            else (
                " Generate portal keys (scripts/generate_portal_jwks_keys.py) and "
                "set PUBLIC_BASE_URL so /.well-known/jwks.json can be registered."
                if not jwks_is_configured(environment=self.jwt_environment)
                else " Set PUBLIC_BASE_URL or PORTAL_JWKS_URI for the absolute JWKS URL."
            )
        )
        env_label = (
            "production" if self.portal_environment == "production" else "test sandbox"
        )
        return ConnectionStatus(
            mode="demo",
            label=f"Demo mode ({env_label})",
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

    def fetch_dashboard(
        self,
        patient_id: str | None = None,
        *,
        access_token: str | None = None,
        auth_method: str | None = None,
        grant_type: str | None = None,
    ) -> PortalDashboard:
        _ = (patient_id, access_token, auth_method, grant_type)
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
            problems=[
                ProblemItem(
                    id="cond-601",
                    name="Type 2 diabetes mellitus",
                    status="confirmed",
                    clinical_status="active",
                    onset="2018-03-12",
                    recorded_date="2018-03-12",
                    category="Problem List Item",
                ),
                ProblemItem(
                    id="cond-602",
                    name="Essential hypertension",
                    status="confirmed",
                    clinical_status="active",
                    onset="2015-11-01",
                    recorded_date="2015-11-01",
                    category="Problem List Item",
                ),
            ],
            diagnoses=[
                DiagnosisItem(
                    id="cond-701",
                    name="Acute low back pain",
                    status="confirmed",
                    clinical_status="active",
                    onset="2026-04-03",
                    recorded_date="2026-04-03",
                    category="Encounter Diagnosis",
                ),
            ],
            medications=[
                MedicationItem(
                    id="med-801",
                    name="Metformin 500 MG Oral Tablet",
                    status="active",
                    dosage="Take 1 tablet by mouth twice daily",
                    authored_on="2026-01-15",
                    prescriber="Dr. Rivera",
                    intent="order",
                ),
                MedicationItem(
                    id="med-802",
                    name="Lisinopril 10 MG Oral Tablet",
                    status="active",
                    dosage="Take 1 tablet by mouth daily",
                    authored_on="2025-11-02",
                    prescriber="Dr. Rivera",
                    intent="order",
                ),
            ],
            allergies=[
                AllergyItem(
                    id="alg-901",
                    name="Penicillin",
                    status="active",
                    criticality="high",
                    reaction="Hives; severe",
                    recorded_date="2012-08-20",
                    category="medication",
                ),
                AllergyItem(
                    id="alg-902",
                    name="Peanuts",
                    status="active",
                    criticality="high",
                    reaction="Anaphylaxis",
                    recorded_date="2005-04-11",
                    category="food",
                ),
            ],
            provider_notes=[
                ProviderNoteItem(
                    id="doc-1001",
                    title="Office visit progress note",
                    status="current",
                    note_type="Progress note",
                    authored_on="2026-06-10",
                    author="Dr. Rivera",
                    summary="Medication review and diabetes follow-up.",
                ),
                ProviderNoteItem(
                    id="doc-1002",
                    title="ED physician note",
                    status="current",
                    note_type="ED note",
                    authored_on="2026-04-03",
                    author="ED Team",
                    summary="Acute back pain evaluation; imaging negative.",
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
        jwt_environment: str | None = None,
        portal_environment: str | None = None,
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
        self.portal_environment = normalize_portal_environment(
            portal_environment or jwt_environment or active_jwt_environment()
        )
        self.jwt_environment = (
            (jwt_environment or "").strip().lower()
            or jwt_environment_for_portal(self.portal_environment)
        )
        if self.jwt_environment in {"prod"}:
            self.jwt_environment = "production"
        if self.jwt_environment in {"sandbox", "non-production"}:
            self.jwt_environment = "nonprod"

    def _jwt_ready(self) -> bool:
        return bool(
            self.token_url
            and self.client_id
            and load_private_pem(environment=self.jwt_environment)
        )

    def _secret_ready(self) -> bool:
        return bool(self.token_url and self.client_id and self.client_secret)

    def _obtain_access_token(self) -> str | None:
        self._last_auth_error = None
        if self._static_access_token:
            self._auth_method = "static_token"
            return self._static_access_token
        if self._cached_access_token:
            return self._cached_access_token

        jwt_env = self.jwt_environment
        if self._jwt_ready():
            pem = load_private_pem(environment=jwt_env)
            assert pem is not None and self.token_url and self.client_id
            try:
                token = request_private_key_jwt_token(
                    token_url=self.token_url,
                    client_id=self.client_id,
                    private_key_pem=pem,
                    scope=self.scope,
                    algorithm=signing_algorithm(environment=jwt_env),
                    kid=signing_kid(environment=jwt_env),
                    jku=public_jwks_uri(environment=jwt_env),
                )
            except (RuntimeError, ValueError, TypeError) as exc:
                self._last_auth_error = (
                    f"JWT private key/assertion failed: {exc}. "
                    "PORTAL_JWT_PRIVATE_KEY must be an RSA PEM private key "
                    "(-----BEGIN PRIVATE KEY-----...), not a JWKS URL."
                )
                return None
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
        jwt_env = self.jwt_environment
        jwks_uri = public_jwks_uri(environment=jwt_env)
        has_static = bool(self._static_access_token)
        jwt_ready = self._jwt_ready()
        secret_ready = self._secret_ready()
        jwks_ready = jwks_is_configured(environment=jwt_env)
        env_label = (
            "production" if self.portal_environment == "production" else "test sandbox"
        )

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
                label=f"Endpoint configured — credentials missing ({env_label})",
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
            else f"Connected (backend services · {env_label})"
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

    def fetch_dashboard(
        self,
        patient_id: str | None = None,
        *,
        access_token: str | None = None,
        auth_method: str | None = None,
        grant_type: str | None = None,
    ) -> PortalDashboard:
        self._last_fetch_notes = []
        resolved_patient_id = (
            (patient_id or "").strip()
            or (self.default_patient_id or "").strip()
            or None
        )

        override_token = (access_token or "").strip() or None
        if override_token:
            self._auth_method = auth_method or "patient_authorization_code"
            obtained_token: str | None = override_token
        else:
            try:
                obtained_token = self._obtain_access_token()
            except (RuntimeError, ValueError, TypeError) as exc:
                self._last_auth_error = str(exc)
                obtained_token = None

        connection = self.get_connection_status()
        if override_token:
            connection.auth_method = auth_method or "patient_authorization_code"
            connection.grant_type = grant_type or "authorization_code"
            connection.label = "Connected (patient Epic login)"
            connection.mode = "live"
            connection.detail = (
                f"FHIR base {self.base_url} with patient authorization_code token."
            )
        if not obtained_token:
            return PortalDashboard(
                connection=connection,
                patient_display_name=resolved_patient_id or "No patient selected",
            )

        access_token = obtained_token

        if not resolved_patient_id:
            self._last_fetch_notes.append(
                "Enter a patient FHIR id in the advocate lookup form, pass "
                f"?patient_id=…, or set FHIR_PATIENT_ID (sandbox test patient: "
                f"{EPIC_SANDBOX_TEST_PATIENT_ID}). "
                "Patient Epic login supplies the patient id from the token response."
            )
            return PortalDashboard(
                connection=connection
                if override_token
                else self.get_connection_status(),
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
        conditions = self._safe_get(
            build_search_url(
                self.base_url,
                "Condition",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )
        medications = self._safe_get(
            build_search_url(
                self.base_url,
                "MedicationRequest",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )
        allergies = self._safe_get(
            build_search_url(
                self.base_url,
                "AllergyIntolerance",
                {"patient": resolved_patient_id},
            ),
            access_token,
        )
        provider_notes = self._safe_get(
            build_search_url(
                self.base_url,
                "DocumentReference",
                {"patient": resolved_patient_id, "category": "clinical-note"},
            ),
            access_token,
        )
        note_entries = []
        if provider_notes:
            if provider_notes.get("resourceType") == "Bundle":
                note_entries = provider_notes.get("entry") or []
            else:
                note_entries = [provider_notes]
        if not note_entries:
            # Some vendors omit category=clinical-note; fall back to all notes.
            provider_notes = self._safe_get(
                build_search_url(
                    self.base_url,
                    "DocumentReference",
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

        if override_token:
            connection.detail = (
                f"FHIR base {self.base_url} with patient authorization_code token. "
                + " ".join(self._last_fetch_notes)
            ).strip()
            final_connection = connection
        else:
            final_connection = self.get_connection_status()

        return PortalDashboard(
            connection=final_connection,
            patient_display_name=patient_display_name(patient)
            if patient
            else resolved_patient_id,
            test_results=map_observations(observations),
            insurance_approvals=map_coverage(coverage),
            procedures=map_procedures(procedures),
            encounters=map_encounters(encounters),
            problems=map_problems(conditions),
            diagnoses=map_diagnoses(conditions),
            medications=map_medications(medications),
            allergies=map_allergies(allergies),
            provider_notes=map_provider_notes(provider_notes),
        )


def get_fhir_client(*, environment: str | None = None) -> FHIRClient:
    """Factory: live client when a FHIR base URL is set, otherwise demo.

    ``environment`` selects sandbox vs production URL/credential/JWT sets.
    """
    settings = resolve_fhir_connection_settings(environment)
    base_url = settings["base_url"]
    if base_url:
        return LiveFHIRClient(
            base_url=base_url,
            token_url=settings["token_url"],
            client_id=settings["client_id"],
            client_secret=settings["client_secret"],
            scope=settings["scope"],
            access_token=settings["access_token"],
            default_patient_id=settings["default_patient_id"],
            jwt_environment=settings["jwt_environment"],
            portal_environment=settings["portal_environment"],
        )
    return DemoFHIRClient(portal_environment=settings["portal_environment"] or "sandbox")
