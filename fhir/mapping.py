"""Map FHIR R4 resources into portal dashboard view models."""

from __future__ import annotations

from typing import Any

from fhir.models import EncounterItem, InsuranceApproval, ProcedureItem, TestResult


def _coding_display(codeable: dict[str, Any] | None) -> str:
    if not codeable:
        return ""
    text = (codeable.get("text") or "").strip()
    if text:
        return text
    for coding in codeable.get("coding") or []:
        display = (coding.get("display") or coding.get("code") or "").strip()
        if display:
            return display
    return ""


def _human_name(name: dict[str, Any] | None) -> str:
    if not name:
        return ""
    text = (name.get("text") or "").strip()
    if text:
        return text
    given = " ".join(g for g in (name.get("given") or []) if g)
    family = (name.get("family") or "").strip()
    return " ".join(part for part in (given, family) if part).strip()


def patient_display_name(patient: dict[str, Any] | None) -> str:
    if not patient:
        return "Unknown Patient"
    names = patient.get("name") or []
    for preferred_use in ("usual", "official", None):
        for name in names:
            if preferred_use is None or name.get("use") == preferred_use:
                display = _human_name(name)
                if display:
                    return display
    return patient.get("id") or "Unknown Patient"


def _bundle_resources(bundle_or_resource: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not bundle_or_resource:
        return []
    if bundle_or_resource.get("resourceType") == "Bundle":
        resources: list[dict[str, Any]] = []
        for entry in bundle_or_resource.get("entry") or []:
            resource = entry.get("resource")
            if isinstance(resource, dict):
                resources.append(resource)
        return resources
    return [bundle_or_resource]


def _observation_value(obs: dict[str, Any]) -> str:
    if "valueQuantity" in obs:
        qty = obs["valueQuantity"] or {}
        value = qty.get("value")
        unit = qty.get("unit") or qty.get("code") or ""
        if value is None:
            return ""
        return f"{value} {unit}".strip()
    if "valueString" in obs:
        return str(obs.get("valueString") or "")
    if "valueCodeableConcept" in obs:
        return _coding_display(obs.get("valueCodeableConcept"))
    components = obs.get("component") or []
    if components:
        parts = []
        for component in components:
            label = _coding_display(component.get("code")) or "component"
            value = _observation_value(component) or "—"
            parts.append(f"{label}: {value}")
        return "; ".join(parts)
    return (obs.get("dataAbsentReason") and _coding_display(obs.get("dataAbsentReason"))) or ""


def map_observations(bundle: dict[str, Any] | None) -> list[TestResult]:
    results: list[TestResult] = []
    for obs in _bundle_resources(bundle):
        if obs.get("resourceType") != "Observation":
            continue
        category = ""
        for cat in obs.get("category") or []:
            category = _coding_display(cat)
            if category:
                break
        performer = ""
        for ref in obs.get("performer") or []:
            performer = (ref.get("display") or "").strip()
            if performer:
                break
        results.append(
            TestResult(
                id=str(obs.get("id") or ""),
                name=_coding_display(obs.get("code")) or "Observation",
                status=str(obs.get("status") or "unknown"),
                result_summary=_observation_value(obs) or "—",
                effective_date=str(
                    obs.get("effectiveDateTime")
                    or obs.get("issued")
                    or (obs.get("effectivePeriod") or {}).get("start")
                    or ""
                ),
                ordered_by=performer,
                category=category or "Laboratory",
            )
        )
    return results


def map_encounters(bundle: dict[str, Any] | None) -> list[EncounterItem]:
    items: list[EncounterItem] = []
    for enc in _bundle_resources(bundle):
        if enc.get("resourceType") != "Encounter":
            continue
        encounter_type = ""
        for type_cc in enc.get("type") or []:
            encounter_type = _coding_display(type_cc)
            if encounter_type:
                break
        if not encounter_type:
            encounter_type = _coding_display(enc.get("class")) or "Encounter"

        when = ""
        period = enc.get("period") or {}
        when = str(period.get("start") or period.get("end") or "")

        location = ""
        for loc in enc.get("location") or []:
            location = ((loc.get("location") or {}).get("display") or "").strip()
            if location:
                break

        reason = ""
        for reason_cc in enc.get("reasonCode") or []:
            reason = _coding_display(reason_cc)
            if reason:
                break

        provider = ""
        for participant in enc.get("participant") or []:
            provider = ((participant.get("individual") or {}).get("display") or "").strip()
            if provider:
                break

        items.append(
            EncounterItem(
                id=str(enc.get("id") or ""),
                encounter_type=encounter_type,
                status=str(enc.get("status") or "unknown"),
                when=when,
                location=location,
                reason=reason,
                provider=provider,
            )
        )
    return items


def map_coverage(bundle: dict[str, Any] | None) -> list[InsuranceApproval]:
    items: list[InsuranceApproval] = []
    for cov in _bundle_resources(bundle):
        if cov.get("resourceType") != "Coverage":
            continue
        payor = ""
        for ref in cov.get("payor") or []:
            payor = (ref.get("display") or "").strip()
            if payor:
                break
        class_name = ""
        for cls in cov.get("class") or []:
            class_name = _coding_display(cls.get("type")) or (cls.get("name") or "")
            if class_name:
                break
        period = cov.get("period") or {}
        items.append(
            InsuranceApproval(
                id=str(cov.get("id") or ""),
                service_name=class_name or "Coverage",
                status=str(cov.get("status") or "unknown"),
                payer=payor or "—",
                decision_date=str(period.get("start") or period.get("end") or ""),
                authorization_number=str(cov.get("subscriberId") or ""),
                notes=_coding_display(cov.get("type")),
            )
        )
    return items


def map_procedures(bundle: dict[str, Any] | None) -> list[ProcedureItem]:
    items: list[ProcedureItem] = []
    for proc in _bundle_resources(bundle):
        if proc.get("resourceType") != "Procedure":
            continue
        performer = ""
        for entry in proc.get("performer") or []:
            actor = entry.get("actor") or {}
            performer = (actor.get("display") or "").strip()
            if performer:
                break
        location = ((proc.get("location") or {}).get("display") or "").strip()
        when = str(
            proc.get("performedDateTime")
            or (proc.get("performedPeriod") or {}).get("start")
            or ""
        )
        items.append(
            ProcedureItem(
                id=str(proc.get("id") or ""),
                name=_coding_display(proc.get("code")) or "Procedure",
                status=str(proc.get("status") or "unknown"),
                scheduled_or_performed=when,
                location=location,
                performer=performer,
            )
        )
    return items
