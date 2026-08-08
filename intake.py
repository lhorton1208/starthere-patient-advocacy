from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import (
    Client,
    Company,
    Encounter,
    Hospital,
    Note,
    Patient,
    _utcnow,
    db,
    link_client_patient,
)
from seed import COMPANY_NAME


def split_name(full_name: str) -> Tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def get_or_create_hospital(
    name: Optional[str],
    *,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> Optional[Hospital]:
    if not name:
        return None
    name = name.strip()
    hospital = Hospital.query.filter_by(name=name).first()
    if not hospital:
        hospital = Hospital(name=name)
        db.session.add(hospital)
        db.session.flush()
    # Fill missing location fields when provided (do not overwrite existing values).
    if address and address.strip() and not hospital.address:
        hospital.address = address.strip()
    if city and city.strip() and not hospital.city:
        hospital.city = city.strip()
    if state and state.strip() and not hospital.state:
        hospital.state = state.strip()
    return hospital


def get_client_by_email(email: str) -> Optional[Client]:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return Client.query.filter_by(email=normalized).first()


def get_patient_by_email(email: str) -> Optional[Patient]:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return Patient.query.filter_by(email=normalized).first()


# Statuses returned by resolve_patient_lookup (HIPAA-safe: no wrong-patient picks).
LOOKUP_FOUND = "found"
LOOKUP_NOT_FOUND = "not_found"
LOOKUP_AMBIGUOUS = "ambiguous"
LOOKUP_INVALID = "invalid"

PATIENT_MUST_EXIST_MESSAGE = (
    "Patient not found. Please insert patient details first before attempting "
    "to request this service."
)

PATIENT_AMBIGUOUS_MESSAGE = (
    "Multiple patients match that name. Enter the Patient ID (from Patient Info) "
    "to request this service — matching by name alone is not allowed when ambiguous."
)

PATIENT_ID_REQUIRED_MESSAGE = (
    "Enter a Patient ID or the patient's exact full name (first and last). "
    "Partial names are not accepted."
)


def _parse_patient_id_token(raw: str) -> Optional[int]:
    """Extract a numeric patient id from values like '12', '#12', or 'ID: 12'."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    stripped = text.lstrip("#").strip()
    if stripped.lower().startswith("id:"):
        stripped = stripped[3:].strip()
    # "Jane Doe (ID 12)" prefill format
    if "ID " in stripped.upper():
        # Find trailing digits after ID
        upper = stripped.upper()
        idx = upper.rfind("ID ")
        if idx >= 0:
            tail = stripped[idx + 3 :].strip().rstrip(")").strip()
            if tail.isdigit():
                return int(tail)
    if stripped.isdigit():
        return int(stripped)
    return None


def resolve_patient_lookup(query: Optional[str]) -> dict:
    """Strict patient resolution for service intake.

    Returns a dict with:
      status: found | not_found | ambiguous | invalid
      patient: Patient | None
      message: str

    Rules (HIPAA-safe):
    - Patient ID always preferred and unambiguous.
    - Full first + last name only when exactly one active match exists.
    - Never return a "best guess" among multiple name matches.
    - No single-token / partial-name matching.
    """
    raw = (query or "").strip()
    if not raw:
        return {
            "status": LOOKUP_INVALID,
            "patient": None,
            "message": PATIENT_ID_REQUIRED_MESSAGE,
        }

    patient_id = _parse_patient_id_token(raw)
    if patient_id is not None:
        patient = Patient.query.get(patient_id)
        if patient:
            return {
                "status": LOOKUP_FOUND,
                "patient": patient,
                "message": f"Patient verified: {patient.full_name} (ID {patient.id})",
            }
        return {
            "status": LOOKUP_NOT_FOUND,
            "patient": None,
            "message": PATIENT_MUST_EXIST_MESSAGE,
        }

    normalized = " ".join(raw.split())
    parts = normalized.split()
    if len(parts) < 2:
        return {
            "status": LOOKUP_INVALID,
            "patient": None,
            "message": PATIENT_ID_REQUIRED_MESSAGE,
        }

    first_name = parts[0]
    last_name = parts[-1]
    matches = (
        Patient.query.filter(
            func.lower(Patient.first_name) == first_name.lower(),
            func.lower(Patient.last_name) == last_name.lower(),
        )
        .order_by(Patient.id.asc())
        .limit(3)
        .all()
    )
    if len(matches) == 1:
        patient = matches[0]
        return {
            "status": LOOKUP_FOUND,
            "patient": patient,
            "message": f"Patient verified: {patient.full_name} (ID {patient.id})",
        }
    if len(matches) > 1:
        return {
            "status": LOOKUP_AMBIGUOUS,
            "patient": None,
            "message": PATIENT_AMBIGUOUS_MESSAGE,
        }
    return {
        "status": LOOKUP_NOT_FOUND,
        "patient": None,
        "message": PATIENT_MUST_EXIST_MESSAGE,
    }


def find_patient_by_name_or_id(query: Optional[str]) -> Optional[Patient]:
    """Return a patient only when the lookup is unambiguous; otherwise None."""
    result = resolve_patient_lookup(query)
    return result["patient"] if result["status"] == LOOKUP_FOUND else None


def get_patient_by_id(patient_id: Optional[int]) -> Optional[Patient]:
    if not patient_id:
        return None
    try:
        pid = int(patient_id)
    except (TypeError, ValueError):
        return None
    return Patient.query.get(pid)


def ensure_client_and_patient(
    *,
    contact_name: str,
    phone: str,
    email: str,
    patient_name: str,
) -> Tuple[Client, Patient]:
    """Create or reuse client + patient records without creating a service encounter.

    Used when Service Request hands off to a dedicated service intake form so a
    new patient is saved before ER / Outpatient metadata is collected.
    """
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        raise RuntimeError("StartHere company record is missing. Run seed_database().")

    patient_name = (patient_name or "").strip()
    if not patient_name:
        raise ValueError(
            "Patient name is required before requesting this service. "
            "Enter the patient's full name so their record can be created."
        )

    client = get_or_create_client(
        company,
        contact_name=contact_name,
        phone=phone,
        email=email,
    )
    patient = create_patient_for_client(
        company,
        client,
        patient_name=patient_name,
        phone=phone,
        email=normalize_email(email),
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            "Could not save patient. Check that client and patient emails are unique."
        ) from exc
    return client, patient


def get_or_create_client(
    company: Company,
    *,
    contact_name: str,
    phone: str,
    email: str,
    address: Optional[str] = None,
) -> Client:
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ValueError("Client email is required.")

    client = get_client_by_email(normalized_email)
    first_name, last_name = split_name(contact_name)
    display = contact_name.strip() or f"{first_name} {last_name}".strip()

    if client:
        client.name = display
        client.first_name = first_name
        client.last_name = last_name
        client.phone = phone.strip() or client.phone
        if address:
            client.address = address.strip()
        client.sync_name_fields()
        return client

    client = Client(
        company_id=company.id,
        name=display,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
        email=normalized_email,
        address=(address or "").strip() or None,
    )
    client.sync_name_fields()
    db.session.add(client)
    db.session.flush()
    return client


def create_patient_for_client(
    company: Company,
    client: Client,
    *,
    patient_name: str,
    phone: str,
    email: Optional[str],
) -> Patient:
    patient_email = normalize_email(email) or client.email
    if not patient_email:
        raise ValueError("Patient email is required when creating a patient.")

    existing_patient = get_patient_by_email(patient_email)
    if existing_patient:
        if existing_patient.client_id != client.id:
            raise ValueError(
                "A patient with this email already exists and is linked to another client."
            )
        link_client_patient(client, existing_patient)
        return existing_patient

    if Patient.query.filter_by(client_id=client.id).first():
        raise ValueError("This client is already linked to a patient.")

    first_name, last_name = split_name(patient_name)
    patient = Patient(
        company_id=company.id,
        client_id=client.id,
        first_name=first_name or "Patient",
        last_name=last_name or "Unknown",
        phone=phone.strip() or None,
        phone_mobile=phone.strip() or None,
        email=patient_email,
        created_by="intake",
    )
    db.session.add(patient)
    db.session.flush()
    link_client_patient(client, patient)
    return patient


def _yes_no_label(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "yes":
        return "Yes"
    if normalized == "no":
        return "No"
    return (value or "").strip() or "Not specified"


def _procedure_visit_type_label(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "initial":
        return "Initial procedure"
    if normalized in {"follow-up", "followup"}:
        return "Follow-up procedure"
    return (value or "").strip() or "Not specified"


def format_outpatient_procedure_notes(
    *,
    procedure_name: str,
    first_time_with_provider: str,
    procedure_visit_type: str,
    provider_name: str,
    provider_office_name: str,
    provider_specialty: str,
    provider_phone: str,
    provider_address: str,
    hipaa_release_for_provider: str,
    notes: Optional[str] = None,
) -> str:
    """Serialize OutPatient Procedure Advocacy form answers into a note body.

    The note is stored on the outpatient-procedure Encounter and Patient so the
    service-specific answers stay attached to both records.
    """
    sections = [
        "OutPatient Procedure Advocacy Intake",
        f"Procedure Name: {procedure_name.strip()}",
        (
            "First time seeing this provider: "
            f"{_yes_no_label(first_time_with_provider)}"
        ),
        (
            "Procedure type: "
            f"{_procedure_visit_type_label(procedure_visit_type)}"
        ),
        "\n".join(
            [
                "Provider Details:",
                f"  Name: {provider_name.strip()}",
                f"  Office Name: {provider_office_name.strip()}",
                f"  Specialty: {provider_specialty.strip()}",
                f"  Phone Number: {provider_phone.strip()}",
                f"  Address: {provider_address.strip()}",
            ]
        ),
        (
            "HIPAA release completed for this provider to share information "
            f"with StartHere: {_yes_no_label(hipaa_release_for_provider)}"
        ),
    ]
    if notes and notes.strip():
        sections.append(f"Additional Notes:\n{notes.strip()}")
    return "\n\n".join(sections)


def format_er_visit_notes(
    *,
    chief_complaint: str,
    first_hospital_encounter: str,
    hospital_name: str,
    hospital_address: str,
    hospital_city: str,
    hospital_state: str,
    nok_name: str,
    nok_phone: str,
    nok_email: Optional[str] = None,
    additional_comments: Optional[str] = None,
) -> str:
    """Serialize ER Visit intake answers into a note body on the encounter/patient."""
    sections = [
        "ER Visit Intake",
        f"Chief Complaint:\n{chief_complaint.strip()}",
        (
            "First hospital encounter for this complaint: "
            f"{_yes_no_label(first_hospital_encounter)}"
        ),
        "\n".join(
            [
                "Hospital:",
                f"  Name: {hospital_name.strip()}",
                f"  Address: {hospital_address.strip()}",
                f"  City: {hospital_city.strip()}",
                f"  State: {hospital_state.strip()}",
            ]
        ),
        "\n".join(
            [
                "Next of Kin:",
                f"  Name: {nok_name.strip()}",
                f"  Phone Number: {nok_phone.strip()}",
                (
                    f"  Email Address: {nok_email.strip()}"
                    if nok_email and nok_email.strip()
                    else "  Email Address: —"
                ),
            ]
        ),
    ]

    if additional_comments and additional_comments.strip():
        sections.append(f"Additional Comments:\n{additional_comments.strip()}")
    return "\n\n".join(sections)


def create_intake_request(
    *,
    patient_name: Optional[str],
    contact_name: str,
    phone: str,
    email: str,
    service: Optional[str] = None,
    hospital_name: Optional[str] = None,
    hospital_address: Optional[str] = None,
    hospital_city: Optional[str] = None,
    hospital_state: Optional[str] = None,
    notes: Optional[str] = None,
    patient_must_exist: bool = False,
    patient_id: Optional[int] = None,
) -> Tuple[Client, Optional[Patient], Optional[Encounter]]:
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        raise RuntimeError("StartHere company record is missing. Run seed_database().")

    client = get_or_create_client(
        company,
        contact_name=contact_name,
        phone=phone,
        email=email,
    )

    patient = None
    encounter = None
    patient_name = (patient_name or "").strip()
    service = (service or "").strip() or None

    if patient_name and not service and not patient_must_exist:
        raise ValueError("Please select a service when submitting patient information.")

    if patient_must_exist:
        # Prefer verified patient_id (set after unambiguous lookup / service-request handoff).
        if patient_id:
            patient = get_patient_by_id(patient_id)
        if not patient and patient_name:
            result = resolve_patient_lookup(patient_name)
            if result["status"] == LOOKUP_AMBIGUOUS:
                raise ValueError(result["message"])
            if result["status"] == LOOKUP_FOUND:
                patient = result["patient"]
        if not patient:
            raise ValueError(PATIENT_MUST_EXIST_MESSAGE)
    elif patient_name:
        patient_email = normalize_email(email)
        patient = create_patient_for_client(
            company,
            client,
            patient_name=patient_name,
            phone=phone,
            email=patient_email,
        )

    if patient and service:
        hospital = get_or_create_hospital(
            hospital_name,
            address=hospital_address,
            city=hospital_city,
            state=hospital_state,
        )
        encounter = Encounter(
            patient_id=patient.id,
            hospital_id=hospital.id if hospital else None,
            encounter_type=service,
            status="requested",
        )
        db.session.add(encounter)
        db.session.flush()

        if notes and notes.strip():
            db.session.add(
                Note(
                    encounter_id=encounter.id,
                    patient_id=patient.id,
                    content=notes.strip(),
                    note_text=notes.strip(),
                    description="Service intake",
                    author=contact_name.strip(),
                    note_datetime=_utcnow(),
                )
            )

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            "Could not save request. Check that client and patient emails are unique."
        ) from exc

    return client, patient, encounter
