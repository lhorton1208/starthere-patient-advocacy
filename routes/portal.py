"""Patient/Advocate Portal — FHIR-backed dashboard.

Access: authenticated advocate (backend services) or patient Epic MyChart
session (SMART App Launch / authorization_code + PKCE).

Patients never enter MyChart credentials on this site — they are redirected to
Epic's authorize page to sign in securely.

Live Epic testing (advocate/backend): set FHIR_* + PORTAL_JWT_* env vars, then
open /portal/dashboard?patient_id=<Epic sandbox patient id>.

Live Epic testing (patient login): register a Patient-audience app on
fhir.epic.com, set FHIR_AUTHORIZE_URL / FHIR_PATIENT_CLIENT_ID /
FHIR_PATIENT_SCOPE / FHIR_REDIRECT_URI (or PUBLIC_BASE_URL), then open
/portal/login and choose Sign in with Epic.
"""

from __future__ import annotations

from urllib.parse import urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth import get_current_advocate
from fhir import get_fhir_client
from fhir.jwks import (
    active_jwt_environment,
    load_private_pem,
    public_jwks_uri,
    signing_algorithm,
    signing_kid,
)
from fhir.oauth import (
    build_authorize_url,
    generate_oauth_state,
    generate_pkce_pair,
    request_authorization_code_token,
)
from fhir.patient_auth import (
    authorize_url,
    clear_epic_patient_session,
    fhir_base_url,
    get_epic_patient_session,
    patient_client_id,
    patient_client_secret,
    patient_oauth_configured,
    patient_scope,
    pop_oauth_pending,
    portal_access_required,
    resolve_redirect_uri,
    store_epic_patient_session,
    store_oauth_pending,
    token_url,
)

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _safe_next_url(target: str | None) -> str | None:
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target


@portal_bp.route("/login")
def login():
    """Patient portal gate — start Epic MyChart OAuth or continue if already signed in."""
    if get_epic_patient_session() is not None or get_current_advocate() is not None:
        next_url = _safe_next_url(request.args.get("next"))
        return redirect(next_url or url_for("portal.dashboard"))

    return render_template(
        "portal/login.html",
        oauth_configured=patient_oauth_configured(),
        authorize_host=authorize_url(),
    )


@portal_bp.route("/epic/login")
def epic_login():
    """Redirect the patient to Epic's authorize page (credentials entered there)."""
    if not patient_oauth_configured():
        flash(
            "Epic patient login is not configured. Set FHIR_AUTHORIZE_URL, "
            "FHIR_TOKEN_URL, and FHIR_PATIENT_CLIENT_ID (or FHIR_CLIENT_ID).",
            "error",
        )
        return redirect(url_for("portal.login"))

    client_id = patient_client_id()
    redirect_uri = resolve_redirect_uri()
    pkce = generate_pkce_pair()
    state = generate_oauth_state()
    store_oauth_pending(state=state, code_verifier=pkce.code_verifier)

    next_url = _safe_next_url(request.args.get("next"))
    if next_url:
        session["epic_oauth_next"] = next_url
        session.modified = True

    url = build_authorize_url(
        authorize_url=authorize_url(),
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=patient_scope(),
        state=state,
        code_challenge=pkce.code_challenge,
        aud=fhir_base_url() or None,
    )
    return redirect(url)


@portal_bp.route("/epic/callback")
def epic_callback():
    """OAuth redirect URI — exchange code for a patient access token."""
    error = request.args.get("error")
    if error:
        description = request.args.get("error_description") or error
        flash(f"Epic sign-in was not completed: {description}", "error")
        clear_epic_patient_session()
        return redirect(url_for("portal.login"))

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state, code_verifier = pop_oauth_pending()

    if not code or not state or not expected_state or state != expected_state:
        flash("Epic sign-in failed (invalid or expired state). Please try again.", "error")
        clear_epic_patient_session()
        return redirect(url_for("portal.login"))

    if not code_verifier:
        flash("Epic sign-in failed (missing PKCE verifier). Please try again.", "error")
        return redirect(url_for("portal.login"))

    client_id = patient_client_id()
    tok_url = token_url()
    if not client_id or not tok_url:
        flash("Epic patient login is not configured on the server.", "error")
        return redirect(url_for("portal.login"))

    jwt_env = active_jwt_environment()
    private_pem = load_private_pem(environment=jwt_env)
    secret = patient_client_secret() or None

    try:
        token = request_authorization_code_token(
            token_url=tok_url,
            client_id=client_id,
            code=code,
            redirect_uri=resolve_redirect_uri(),
            code_verifier=code_verifier,
            client_secret=None if private_pem else secret,
            private_key_pem=private_pem,
            algorithm=signing_algorithm(environment=jwt_env),
            kid=signing_kid(environment=jwt_env),
            jku=public_jwks_uri(environment=jwt_env),
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        flash(f"Could not complete Epic sign-in: {exc}", "error")
        return redirect(url_for("portal.login"))

    store_epic_patient_session(
        access_token=token.access_token,
        patient_id=token.patient,
        scope=token.scope,
        expires_in=token.expires_in,
    )

    next_url = _safe_next_url(session.pop("epic_oauth_next", None))
    flash("Signed in with Epic. Your chart data is loading.", "success")
    return redirect(next_url or url_for("portal.dashboard"))


@portal_bp.route("/epic/logout")
def epic_logout():
    clear_epic_patient_session()
    flash("You have been signed out of Epic.", "success")
    return redirect(url_for("portal.login"))


@portal_bp.route("/")
@portal_bp.route("/dashboard")
@portal_access_required
def dashboard():
    """Display FHIR-sourced clinical and administrative information.

    Patient Epic sessions use the authorization_code access token and the
    `patient` id returned by Epic. Advocates use Backend Services and optional
    `?patient_id=` (falls back to FHIR_PATIENT_ID).
    """
    epic = get_epic_patient_session()
    client = get_fhir_client()

    if epic is not None:
        patient_id = epic.patient_id or request.args.get("patient_id") or None
        data = client.fetch_dashboard(
            patient_id=patient_id,
            access_token=epic.access_token,
            auth_method="patient_authorization_code",
            grant_type="authorization_code",
        )
    else:
        patient_id = request.args.get("patient_id") or None
        data = client.fetch_dashboard(patient_id=patient_id)

    if not data.connection.jwks_uri:
        data.connection.jwks_uri = public_jwks_uri(
            preferred_base=request.url_root.rstrip("/")
        )
    return render_template(
        "portal/dashboard.html",
        dashboard=data,
        epic_patient=epic,
        is_advocate=get_current_advocate() is not None,
    )
