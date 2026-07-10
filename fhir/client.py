"""FHIR client interface and demo implementation.

Replace DemoFHIRClient with a live HTTP client (SMART on FHIR / OAuth2)
once a vendor endpoint and credentials are configured. Keep mapping logic
in `_map_*` helpers so the dashboard contract stays unchanged.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from fhir.models import (
    ConnectionStatus,
    EncounterItem,
    InsuranceApproval,
    PortalDashboard,
    ProcedureItem,
    TestResult,
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
        return ConnectionStatus(
            mode="demo",
            label="Demo mode",
            detail=(
                "Showing sample FHIR-shaped data. Connect a vendor base URL and "
                "credentials to load live test results, approvals, procedures, "
                "and encounters."
            ),
            base_url=None,
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
    """Placeholder for a real FHIR R4 HTTP client.

    Wire SMART on FHIR / OAuth2 token exchange here, then GET:
      {base}/Observation?patient={id}
      {base}/DiagnosticReport?patient={id}
      {base}/Encounter?patient={id}
      {base}/ServiceRequest?patient={id}
      {base}/Procedure?patient={id}
      {base}/ClaimResponse?patient={id}   (or vendor-specific prior-auth)
    """

    def __init__(self, base_url: str, access_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token

    def get_connection_status(self) -> ConnectionStatus:
        if not self.access_token:
            return ConnectionStatus(
                mode="unconfigured",
                label="Endpoint configured — not authenticated",
                detail=(
                    "FHIR_BASE_URL is set, but no access token is available yet. "
                    "Complete patient/advocate login and vendor authorization to "
                    "load live data."
                ),
                base_url=self.base_url,
            )
        return ConnectionStatus(
            mode="live",
            label="Connected",
            detail=f"Querying FHIR endpoint at {self.base_url}",
            base_url=self.base_url,
        )

    def fetch_dashboard(self, patient_id: str | None = None) -> PortalDashboard:
        # TODO: Implement HTTP GETs + Bundle parsing. Until then, fall back to
        # demo data so the dashboard remains usable during development.
        demo = DemoFHIRClient().fetch_dashboard(patient_id)
        demo.connection = self.get_connection_status()
        demo.patient_display_name = patient_id or "Connected Patient"
        return demo


def get_fhir_client() -> FHIRClient:
    """Factory: live client when FHIR_BASE_URL is set, otherwise demo."""
    base_url = os.environ.get("FHIR_BASE_URL", "").strip()
    if base_url:
        token = os.environ.get("FHIR_ACCESS_TOKEN", "").strip() or None
        return LiveFHIRClient(base_url=base_url, access_token=token)
    return DemoFHIRClient()
