"""Normalized portal view models derived from FHIR resources.

These dataclasses are what the Dashboard renders. The FHIR client maps
vendor responses (Observation, Encounter, Condition, etc.) into these
shapes so the UI stays stable as vendor endpoints change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ConnectionMode = Literal["demo", "live", "unconfigured"]


@dataclass
class ConnectionStatus:
    mode: ConnectionMode
    label: str
    detail: str
    base_url: str | None = None
    jwks_uri: str | None = None
    auth_method: str | None = None
    grant_type: str | None = None


@dataclass
class TestResult:
    id: str
    name: str
    status: str
    result_summary: str
    effective_date: str
    ordered_by: str = ""
    category: str = "Laboratory"


@dataclass
class InsuranceApproval:
    id: str
    service_name: str
    status: str
    payer: str
    decision_date: str
    authorization_number: str = ""
    notes: str = ""


@dataclass
class ProcedureItem:
    id: str
    name: str
    status: str
    scheduled_or_performed: str
    location: str = ""
    performer: str = ""


@dataclass
class EncounterItem:
    id: str
    encounter_type: str
    status: str
    when: str
    location: str = ""
    reason: str = ""
    provider: str = ""


@dataclass
class ProblemItem:
    """Active problem-list Condition (category problem-list-item)."""

    id: str
    name: str
    status: str
    clinical_status: str = ""
    onset: str = ""
    recorded_date: str = ""
    category: str = ""


@dataclass
class DiagnosisItem:
    """Encounter or clinical diagnosis Condition (category encounter-diagnosis)."""

    id: str
    name: str
    status: str
    clinical_status: str = ""
    onset: str = ""
    recorded_date: str = ""
    category: str = ""


@dataclass
class MedicationItem:
    """MedicationRequest (orders / active prescriptions)."""

    id: str
    name: str
    status: str
    dosage: str = ""
    authored_on: str = ""
    prescriber: str = ""
    intent: str = ""


@dataclass
class AllergyItem:
    """AllergyIntolerance resource."""

    id: str
    name: str
    status: str
    criticality: str = ""
    reaction: str = ""
    recorded_date: str = ""
    category: str = ""


@dataclass
class ProviderNoteItem:
    """Clinical note metadata from DocumentReference."""

    id: str
    title: str
    status: str
    note_type: str = ""
    authored_on: str = ""
    author: str = ""
    summary: str = ""


@dataclass
class PortalDashboard:
    """Aggregate payload for the Patient/Advocate Portal dashboard."""

    connection: ConnectionStatus
    patient_display_name: str
    test_results: list[TestResult] = field(default_factory=list)
    insurance_approvals: list[InsuranceApproval] = field(default_factory=list)
    procedures: list[ProcedureItem] = field(default_factory=list)
    encounters: list[EncounterItem] = field(default_factory=list)
    problems: list[ProblemItem] = field(default_factory=list)
    diagnoses: list[DiagnosisItem] = field(default_factory=list)
    medications: list[MedicationItem] = field(default_factory=list)
    allergies: list[AllergyItem] = field(default_factory=list)
    provider_notes: list[ProviderNoteItem] = field(default_factory=list)

    @property
    def summary_counts(self) -> dict[str, int]:
        return {
            "test_results": len(self.test_results),
            "insurance_approvals": len(self.insurance_approvals),
            "procedures": len(self.procedures),
            "encounters": len(self.encounters),
            "problems": len(self.problems),
            "diagnoses": len(self.diagnoses),
            "medications": len(self.medications),
            "allergies": len(self.allergies),
            "provider_notes": len(self.provider_notes),
        }
