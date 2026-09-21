"""Map FHIR R4 resources into portal dashboard view models."""

from __future__ import annotations

from typing import Any

from fhir.models import (
    AllergyItem,
    DiagnosisItem,
    EncounterItem,
    InsuranceApproval,
    MedicationItem,
    ProblemItem,
    ProcedureItem,
    ProviderNoteItem,
    TestResult,
)


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


def _category_tokens(resource: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for cat in resource.get("category") or []:
        if isinstance(cat, str):
            tokens.add(cat.strip().lower())
            continue
        text = (cat.get("text") or "").strip().lower()
        if text:
            tokens.add(text)
        for coding in cat.get("coding") or []:
            for key in ("code", "display"):
                value = (coding.get(key) or "").strip().lower()
                if value:
                    tokens.add(value)
    return tokens


def _condition_onset(cond: dict[str, Any]) -> str:
    return str(
        cond.get("onsetDateTime")
        or (cond.get("onsetPeriod") or {}).get("start")
        or cond.get("onsetString")
        or ""
    )


def _condition_category_label(cond: dict[str, Any]) -> str:
    for cat in cond.get("category") or []:
        label = _coding_display(cat)
        if label:
            return label
    return ""


def _is_problem_condition(tokens: set[str]) -> bool:
    problem_markers = {
        "problem-list-item",
        "problem list item",
        "problem",
        "health-concern",
        "health concern",
    }
    diagnosis_markers = {"encounter-diagnosis", "encounter diagnosis"}
    if tokens & problem_markers:
        return True
    if tokens & diagnosis_markers:
        return False
    # Uncategorized Conditions are treated as problem-list entries.
    return True


def _is_diagnosis_condition(tokens: set[str]) -> bool:
    return bool(
        tokens
        & {
            "encounter-diagnosis",
            "encounter diagnosis",
            "diagnosis",
        }
    )


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


def map_problems(bundle: dict[str, Any] | None) -> list[ProblemItem]:
    items: list[ProblemItem] = []
    for cond in _bundle_resources(bundle):
        if cond.get("resourceType") != "Condition":
            continue
        tokens = _category_tokens(cond)
        if not _is_problem_condition(tokens):
            continue
        verification = cond.get("verificationStatus")
        items.append(
            ProblemItem(
                id=str(cond.get("id") or ""),
                name=_coding_display(cond.get("code")) or "Condition",
                status=_coding_display(verification) or "unknown",
                clinical_status=_coding_display(cond.get("clinicalStatus")),
                onset=_condition_onset(cond),
                recorded_date=str(cond.get("recordedDate") or ""),
                category=_condition_category_label(cond) or "Problem",
            )
        )
    return items


def map_diagnoses(bundle: dict[str, Any] | None) -> list[DiagnosisItem]:
    items: list[DiagnosisItem] = []
    for cond in _bundle_resources(bundle):
        if cond.get("resourceType") != "Condition":
            continue
        tokens = _category_tokens(cond)
        if not _is_diagnosis_condition(tokens):
            continue
        verification = cond.get("verificationStatus")
        items.append(
            DiagnosisItem(
                id=str(cond.get("id") or ""),
                name=_coding_display(cond.get("code")) or "Diagnosis",
                status=_coding_display(verification) or "unknown",
                clinical_status=_coding_display(cond.get("clinicalStatus")),
                onset=_condition_onset(cond),
                recorded_date=str(cond.get("recordedDate") or ""),
                category=_condition_category_label(cond) or "Diagnosis",
            )
        )
    return items


def _medication_name(med: dict[str, Any]) -> str:
    if med.get("medicationCodeableConcept"):
        return _coding_display(med.get("medicationCodeableConcept")) or "Medication"
    reference = med.get("medicationReference") or {}
    display = (reference.get("display") or "").strip()
    if display:
        return display
    return "Medication"


def _medication_dosage(med: dict[str, Any]) -> str:
    parts: list[str] = []
    for instruction in med.get("dosageInstruction") or []:
        text = (instruction.get("text") or "").strip()
        if text:
            parts.append(text)
            continue
        timing = instruction.get("timing") or {}
        timing_code = _coding_display(timing.get("code"))
        dose = ""
        for dose_and_rate in instruction.get("doseAndRate") or []:
            qty = dose_and_rate.get("doseQuantity") or {}
            if qty.get("value") is not None:
                unit = qty.get("unit") or qty.get("code") or ""
                dose = f"{qty.get('value')} {unit}".strip()
                break
        route = _coding_display(instruction.get("route"))
        chunk = " ".join(part for part in (dose, route, timing_code) if part)
        if chunk:
            parts.append(chunk)
    return "; ".join(parts)


def map_medications(bundle: dict[str, Any] | None) -> list[MedicationItem]:
    items: list[MedicationItem] = []
    for med in _bundle_resources(bundle):
        if med.get("resourceType") != "MedicationRequest":
            continue
        prescriber = ((med.get("requester") or {}).get("display") or "").strip()
        items.append(
            MedicationItem(
                id=str(med.get("id") or ""),
                name=_medication_name(med),
                status=str(med.get("status") or "unknown"),
                dosage=_medication_dosage(med),
                authored_on=str(med.get("authoredOn") or ""),
                prescriber=prescriber,
                intent=str(med.get("intent") or ""),
            )
        )
    return items


def map_allergies(bundle: dict[str, Any] | None) -> list[AllergyItem]:
    items: list[AllergyItem] = []
    for allergy in _bundle_resources(bundle):
        if allergy.get("resourceType") != "AllergyIntolerance":
            continue
        categories = allergy.get("category") or []
        category = ", ".join(str(c) for c in categories if c) if categories else ""
        reaction_parts: list[str] = []
        for reaction in allergy.get("reaction") or []:
            for manifestation in reaction.get("manifestation") or []:
                label = _coding_display(manifestation)
                if label:
                    reaction_parts.append(label)
            severity = (reaction.get("severity") or "").strip()
            if severity:
                reaction_parts.append(severity)
        status = (
            _coding_display(allergy.get("clinicalStatus"))
            or _coding_display(allergy.get("verificationStatus"))
            or "unknown"
        )
        items.append(
            AllergyItem(
                id=str(allergy.get("id") or ""),
                name=_coding_display(allergy.get("code")) or "Allergy",
                status=status,
                criticality=str(allergy.get("criticality") or ""),
                reaction="; ".join(reaction_parts),
                recorded_date=str(
                    allergy.get("recordedDate") or allergy.get("onsetDateTime") or ""
                ),
                category=category,
            )
        )
    return items


def map_provider_notes(bundle: dict[str, Any] | None) -> list[ProviderNoteItem]:
    items: list[ProviderNoteItem] = []
    for doc in _bundle_resources(bundle):
        if doc.get("resourceType") != "DocumentReference":
            continue
        note_type = _coding_display(doc.get("type"))
        if not note_type:
            for cat in doc.get("category") or []:
                note_type = _coding_display(cat)
                if note_type:
                    break
        author = ""
        for ref in doc.get("author") or []:
            author = (ref.get("display") or "").strip()
            if author:
                break
        description = (doc.get("description") or "").strip()
        content_titles = []
        for content in doc.get("content") or []:
            attachment = content.get("attachment") or {}
            title = (attachment.get("title") or "").strip()
            if title:
                content_titles.append(title)
        title = (
            description
            or (content_titles[0] if content_titles else "")
            or note_type
            or "Clinical note"
        )
        summary = ""
        if description and description != title:
            summary = description
        elif content_titles and content_titles[0] != title:
            summary = content_titles[0]
        items.append(
            ProviderNoteItem(
                id=str(doc.get("id") or ""),
                title=title,
                status=str(doc.get("status") or "unknown"),
                note_type=note_type or "Clinical note",
                authored_on=str(
                    doc.get("date")
                    or ((doc.get("context") or {}).get("period") or {}).get("start")
                    or ""
                ),
                author=author,
                summary=summary,
            )
        )
    return items
