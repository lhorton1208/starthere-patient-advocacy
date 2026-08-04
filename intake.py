from typing import Optional, Tuple

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


def get_or_create_hospital(name: Optional[str]) -> Optional[Hospital]:
    if not name:
        return None
    hospital = Hospital.query.filter_by(name=name).first()
    if hospital:
        return hospital
    hospital = Hospital(name=name)
    db.session.add(hospital)
    db.session.flush()
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


def create_intake_request(
    *,
    patient_name: Optional[str],
    contact_name: str,
    phone: str,
    email: str,
    service: Optional[str] = None,
    hospital_name: Optional[str] = None,
    notes: Optional[str] = None,
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

    if patient_name and not service:
        raise ValueError("Please select a service when submitting patient information.")

    if patient_name:
        patient_email = normalize_email(email)
        if patient_email and patient_email == client.email:
            patient = create_patient_for_client(
                company,
                client,
                patient_name=patient_name,
                phone=phone,
                email=patient_email,
            )
        else:
            patient = create_patient_for_client(
                company,
                client,
                patient_name=patient_name,
                phone=phone,
                email=patient_email,
            )

        if service:
            hospital = get_or_create_hospital(hospital_name)
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
                        description=notes.strip()[:255],
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
