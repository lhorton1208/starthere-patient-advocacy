"""Patient/Advocate Portal — FHIR-backed dashboard.

Requires an authenticated advocate login (@employee_required). JWKS endpoints
used for FHIR vendor registration remain public on the main app.

Live Epic testing: log in as an advocate, set FHIR_* + PORTAL_JWT_* env vars,
then open /portal/dashboard?patient_id=<Epic sandbox patient id>.
"""

from flask import Blueprint, render_template, request

from auth import employee_required
from fhir import get_fhir_client
from fhir.jwks import public_jwks_uri

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


@portal_bp.route("/")
@portal_bp.route("/dashboard")
@employee_required
def dashboard():
    """Display FHIR-sourced clinical and administrative information.

    Query param `patient_id` scopes live Patient/{id} searches (falls back to
    FHIR_PATIENT_ID when set).
    """
    client = get_fhir_client()
    patient_id = request.args.get("patient_id") or None
    data = client.fetch_dashboard(patient_id=patient_id)
    if not data.connection.jwks_uri:
        data.connection.jwks_uri = public_jwks_uri(
            preferred_base=request.url_root.rstrip("/")
        )
    return render_template("portal/dashboard.html", dashboard=data)
