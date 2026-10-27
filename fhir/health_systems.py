"""Resolve the MyChart authorize, token, and FHIR base URLs for a health system.

One Epic production client ID is shared by every live health system. The Epic
sandbox uses a separate non-production client ID. The three URLs come from the
health_systems row tied to a StartHere client, or from an explicit choice on
the portal login page.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.exc import OperationalError, ProgrammingError

from fhir.patient_auth import authorize_url, fhir_base_url, patient_client_id, token_url
from models import Client, HealthSystem, db

# Inserted when missing. Existing rows are left alone so later edits stick.
DEFAULT_HEALTH_SYSTEMS = (
    {
        "slug": "epic-sandbox",
        "name": "Epic sandbox",
        "fhir_base_url": "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        "authorize_url": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        "token_url": "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        "use_sandbox_client": True,
        "sort_order": 0,
    },
    {
        "slug": "unc",
        "name": "UNC Health Care",
        "fhir_base_url": "https://epicfe.unch.unc.edu/FHIR/api/FHIR/R4",
        "authorize_url": "https://epicfe.unch.unc.edu/FHIR/oauth2/authorize",
        "token_url": "https://epicfe.unch.unc.edu/FHIR/oauth2/token",
        "use_sandbox_client": False,
        "sort_order": 10,
    },
    {
        "slug": "duke",
        "name": "Duke University Health System",
        "fhir_base_url": "https://health-apis.duke.edu/FHIR/api/FHIR/R4",
        "authorize_url": "https://health-apis.duke.edu/FHIR/oauth2/authorize",
        "token_url": "https://health-apis.duke.edu/FHIR/oauth2/token",
        "use_sandbox_client": False,
        "sort_order": 20,
    },
)


@dataclass
class PatientConnection:
    authorize_url: str
    token_url: str
    fhir_base_url: str
    epic_client_id: str
    health_system_id: int | None = None
    health_system_name: str = ""
    health_system_slug: str = ""
    starthere_client_id: int | None = None


def sandbox_patient_client_id() -> str:
    """Non-production Epic client ID. Never falls back to the production ID."""
    return os.environ.get("FHIR_PATIENT_SANDBOX_CLIENT_ID", "").strip()


def epic_client_id_for(system: HealthSystem) -> str:
    if system.use_sandbox_client:
        return sandbox_patient_client_id()
    return patient_client_id()


def seed_health_systems() -> None:
    for row in DEFAULT_HEALTH_SYSTEMS:
        exists = HealthSystem.query.filter_by(slug=row["slug"]).first()
        if exists:
            continue
        db.session.add(HealthSystem(**row))


def active_health_systems() -> list[HealthSystem]:
    try:
        return (
            HealthSystem.query.filter_by(active=True)
            .order_by(HealthSystem.sort_order, HealthSystem.name)
            .all()
        )
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return []


def connection_for_system(
    system: HealthSystem, *, starthere_client_id: int | None = None
) -> PatientConnection | None:
    epic_client_id = epic_client_id_for(system)
    if not (
        system.authorize_url
        and system.token_url
        and system.fhir_base_url
        and epic_client_id
    ):
        return None
    return PatientConnection(
        authorize_url=system.authorize_url.strip(),
        token_url=system.token_url.strip(),
        fhir_base_url=system.fhir_base_url.strip().rstrip("/"),
        epic_client_id=epic_client_id,
        health_system_id=system.id,
        health_system_name=system.name,
        health_system_slug=system.slug,
        starthere_client_id=starthere_client_id,
    )


def env_patient_connection() -> PatientConnection | None:
    """Single-endpoint fallback used when no health system was selected."""
    auth = authorize_url()
    tok = token_url()
    base = fhir_base_url()
    epic_client_id = patient_client_id()
    if not (auth and tok and epic_client_id):
        return None
    return PatientConnection(
        authorize_url=auth,
        token_url=tok,
        fhir_base_url=(base or "").rstrip("/"),
        epic_client_id=epic_client_id,
        health_system_name="Configured endpoint",
    )


def resolve_patient_connection(
    *, system_slug: str | None = None, client_id: int | None = None
) -> PatientConnection | None:
    """Pick URLs from a health-system slug or from the StartHere client's system."""
    starthere_client_id = None
    system = None
    if client_id:
        try:
            client = db.session.get(Client, client_id)
        except (OperationalError, ProgrammingError):
            db.session.rollback()
            client = None
        if client is None or client.health_system is None or not client.health_system.active:
            return None
        system = client.health_system
        starthere_client_id = client.id
    elif system_slug:
        try:
            system = HealthSystem.query.filter_by(slug=system_slug.strip(), active=True).first()
        except (OperationalError, ProgrammingError):
            db.session.rollback()
            system = None
        if system is None:
            return None
    else:
        return None
    return connection_for_system(system, starthere_client_id=starthere_client_id)
