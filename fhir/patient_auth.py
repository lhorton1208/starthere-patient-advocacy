"""Session helpers and config for patient Epic / SMART App Launch login.

Product path: patients sign in with MyChart (authorization_code + PKCE).
Backend Services remain for advocates (sandbox + optional partner orgs).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import wraps

from flask import flash, redirect, request, session, url_for

from auth import get_current_advocate

SESSION_EPIC_ACCESS_TOKEN = "epic_access_token"
SESSION_EPIC_PATIENT_ID = "epic_patient_id"
SESSION_EPIC_SCOPE = "epic_scope"
SESSION_EPIC_EXPIRES_AT = "epic_expires_at"
SESSION_EPIC_FHIR_BASE = "epic_fhir_base_url"
SESSION_EPIC_OAUTH_STATE = "epic_oauth_state"
SESSION_EPIC_CODE_VERIFIER = "epic_code_verifier"
SESSION_EPIC_OAUTH_TOKEN_URL = "epic_oauth_token_url"
SESSION_EPIC_OAUTH_FHIR_BASE = "epic_oauth_fhir_base"
SESSION_EPIC_OAUTH_CLIENT_ID = "epic_oauth_client_id"
SESSION_EPIC_OAUTH_HEALTH_SYSTEM_ID = "epic_oauth_health_system_id"
SESSION_EPIC_OAUTH_HEALTH_SYSTEM_NAME = "epic_oauth_health_system_name"
SESSION_EPIC_HEALTH_SYSTEM_NAME = "epic_health_system_name"

DEFAULT_AUTHORIZE_URL = (
    "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"
)
DEFAULT_PATIENT_SCOPE = (
    "launch/patient openid fhirUser "
    "patient/Patient.read patient/Observation.read patient/Encounter.read "
    "patient/Coverage.read patient/Procedure.read patient/Condition.read "
    "patient/MedicationRequest.read patient/AllergyIntolerance.read "
    "patient/DocumentReference.read"
)


@dataclass
class EpicPatientSession:
    access_token: str
    patient_id: str | None = None
    scope: str | None = None
    expires_at: float | None = None
    fhir_base_url: str | None = None
    health_system_name: str | None = None


@dataclass
class OAuthPending:
    state: str | None
    code_verifier: str | None
    token_url: str | None = None
    fhir_base_url: str | None = None
    epic_client_id: str | None = None
    health_system_id: int | None = None
    health_system_name: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at


def patient_client_id() -> str:
    """Patient-audience Client ID only (do not fall back to Backend Systems ID)."""
    return os.environ.get("FHIR_PATIENT_CLIENT_ID", "").strip()


def patient_scope() -> str:
    return (
        os.environ.get("FHIR_PATIENT_SCOPE", "").strip() or DEFAULT_PATIENT_SCOPE
    )


def authorize_url() -> str:
    return (
        os.environ.get("FHIR_AUTHORIZE_URL", "").strip()
        or os.environ.get("FHIR_PATIENT_AUTHORIZE_URL", "").strip()
        or DEFAULT_AUTHORIZE_URL
    )


def token_url() -> str:
    return (
        os.environ.get("FHIR_PATIENT_TOKEN_URL", "").strip()
        or os.environ.get("FHIR_TOKEN_URL", "").strip()
    )


def fhir_base_url() -> str:
    """FHIR R4 base used as SMART `aud` and for patient chart fetches."""
    return (
        os.environ.get("FHIR_PATIENT_BASE_URL", "").strip()
        or os.environ.get("FHIR_BASE_URL", "").strip()
    )


def patient_client_secret() -> str:
    return os.environ.get("FHIR_PATIENT_CLIENT_SECRET", "").strip()


def resolve_redirect_uri() -> str:
    """Absolute redirect URI registered with Epic for the patient app."""
    explicit = os.environ.get("FHIR_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    public_base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base:
        return f"{public_base}/portal/epic/callback"
    return url_for("portal.epic_callback", _external=True)


def patient_oauth_configured() -> bool:
    return bool(patient_client_id() and token_url() and authorize_url())


def patient_confidential_jwt_enabled() -> bool:
    """Use private_key_jwt on the patient token exchange.

    Only enable when the Epic Patients app has "Is Confidential Client"
    checked and JWKS URLs are registered. Default is public client + PKCE.
    """
    flag = os.environ.get("FHIR_PATIENT_CONFIDENTIAL", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def partner_backend_enabled() -> bool:
    """Whether advocates may use partner/production Backend Services lookup.

    Opt-in only via PORTAL_ALLOW_PARTNER_BACKEND=true. Patients use MyChart;
    production Backend Services is for specific partner orgs after
    FHIR_PRODUCTION_* URLs are configured.
    """
    flag = os.environ.get("PORTAL_ALLOW_PARTNER_BACKEND", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def get_epic_patient_session() -> EpicPatientSession | None:
    token = session.get(SESSION_EPIC_ACCESS_TOKEN)
    if not token:
        return None
    epic = EpicPatientSession(
        access_token=token,
        patient_id=session.get(SESSION_EPIC_PATIENT_ID),
        scope=session.get(SESSION_EPIC_SCOPE),
        expires_at=session.get(SESSION_EPIC_EXPIRES_AT),
        fhir_base_url=session.get(SESSION_EPIC_FHIR_BASE) or None,
        health_system_name=session.get(SESSION_EPIC_HEALTH_SYSTEM_NAME) or None,
    )
    if epic.is_expired:
        clear_epic_patient_session()
        return None
    return epic


def store_epic_patient_session(
    *,
    access_token: str,
    patient_id: str | None = None,
    scope: str | None = None,
    expires_in: int | None = None,
    fhir_base: str | None = None,
    health_system_name: str | None = None,
) -> None:
    session[SESSION_EPIC_ACCESS_TOKEN] = access_token
    if patient_id:
        session[SESSION_EPIC_PATIENT_ID] = patient_id
    elif SESSION_EPIC_PATIENT_ID in session:
        session.pop(SESSION_EPIC_PATIENT_ID, None)
    if scope:
        session[SESSION_EPIC_SCOPE] = scope
    if expires_in:
        # Refresh a minute early so the dashboard does not use a near-dead token.
        session[SESSION_EPIC_EXPIRES_AT] = time.time() + max(expires_in - 60, 0)
    base = (fhir_base or fhir_base_url() or "").strip().rstrip("/")
    if base:
        session[SESSION_EPIC_FHIR_BASE] = base
    if health_system_name:
        session[SESSION_EPIC_HEALTH_SYSTEM_NAME] = health_system_name
    elif SESSION_EPIC_HEALTH_SYSTEM_NAME in session:
        session.pop(SESSION_EPIC_HEALTH_SYSTEM_NAME, None)
    session.modified = True


def clear_epic_patient_session() -> None:
    for key in (
        SESSION_EPIC_ACCESS_TOKEN,
        SESSION_EPIC_PATIENT_ID,
        SESSION_EPIC_SCOPE,
        SESSION_EPIC_EXPIRES_AT,
        SESSION_EPIC_FHIR_BASE,
        SESSION_EPIC_OAUTH_STATE,
        SESSION_EPIC_CODE_VERIFIER,
        SESSION_EPIC_OAUTH_TOKEN_URL,
        SESSION_EPIC_OAUTH_FHIR_BASE,
        SESSION_EPIC_OAUTH_CLIENT_ID,
        SESSION_EPIC_OAUTH_HEALTH_SYSTEM_ID,
        SESSION_EPIC_OAUTH_HEALTH_SYSTEM_NAME,
        SESSION_EPIC_HEALTH_SYSTEM_NAME,
    ):
        session.pop(key, None)
    session.modified = True


def store_oauth_pending(
    *,
    state: str,
    code_verifier: str,
    token_url: str | None = None,
    fhir_base_url: str | None = None,
    epic_client_id: str | None = None,
    health_system_id: int | None = None,
    health_system_name: str | None = None,
) -> None:
    session[SESSION_EPIC_OAUTH_STATE] = state
    session[SESSION_EPIC_CODE_VERIFIER] = code_verifier
    extras = {
        SESSION_EPIC_OAUTH_TOKEN_URL: token_url,
        SESSION_EPIC_OAUTH_FHIR_BASE: fhir_base_url,
        SESSION_EPIC_OAUTH_CLIENT_ID: epic_client_id,
        SESSION_EPIC_OAUTH_HEALTH_SYSTEM_ID: health_system_id,
        SESSION_EPIC_OAUTH_HEALTH_SYSTEM_NAME: health_system_name,
    }
    for key, value in extras.items():
        if value is None or value == "":
            session.pop(key, None)
        else:
            session[key] = value
    session.modified = True


def pop_oauth_pending() -> OAuthPending:
    pending = OAuthPending(
        state=session.pop(SESSION_EPIC_OAUTH_STATE, None),
        code_verifier=session.pop(SESSION_EPIC_CODE_VERIFIER, None),
        token_url=session.pop(SESSION_EPIC_OAUTH_TOKEN_URL, None),
        fhir_base_url=session.pop(SESSION_EPIC_OAUTH_FHIR_BASE, None),
        epic_client_id=session.pop(SESSION_EPIC_OAUTH_CLIENT_ID, None),
        health_system_id=session.pop(SESSION_EPIC_OAUTH_HEALTH_SYSTEM_ID, None),
        health_system_name=session.pop(SESSION_EPIC_OAUTH_HEALTH_SYSTEM_NAME, None),
    )
    session.modified = True
    return pending


def portal_access_required(view):
    """Allow portal access for an advocate or a patient with an Epic session."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_advocate() is not None or get_epic_patient_session() is not None:
            return view(*args, **kwargs)
        flash(
            "Please sign in with Epic / MyChart to view the patient portal.",
            "error",
        )
        return redirect(url_for("portal.login", next=request.full_path))

    return wrapped
