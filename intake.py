from typing import Optional, Tuple

from models import (
    Client,
    Company,
    Encounter,
    Hospital,
    Note,
    Patient,
    db,
)
from seed import COMPANY_NAME


def split_name(full_name: str) -> Tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


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


def get_or_create_client(company: Company, name: str, phone: str, email: str) -> Client:
    normalized_email = email.strip().lower()
    client = Client.query.filter_by(
        company_id=company.id, email=normalized_email
    ).first()
    if client:
        client.name = name.strip()
        client.phone = phone.strip()
        return client

    client = Client(
        company_id=company.id,
        name=name.strip(),
        phone=phone.strip(),
        email=normalized_email,
    )
    db.session.add(client)
    db.session.flush()
    return client


def create_intake_request(
    *,
    patient_name: str,
    contact_name: str,
    phone: str,
    email: str,
    service: str,
    hospital_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> Encounter:
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        raise RuntimeError("StartHere company record is missing. Run seed_database().")

    client = get_or_create_client(company, contact_name, phone, email)
    first_name, last_name = split_name(patient_name)

    patient = Patient(
        company_id=company.id,
        client_id=client.id,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
        email=email.strip().lower(),
    )
    db.session.add(patient)
    db.session.flush()

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
                content=notes.strip(),
                author=contact_name.strip(),
            )
        )

    db.session.commit()
    return encounter
