"""Patient/Advocate Portal — FHIR-backed dashboard.

Currently public so stakeholders can review the dashboard layout. When
patient/advocate credentials and vendor OAuth are ready, gate these routes
with a portal-specific auth decorator (separate from staff @employee_required).

Live Epic testing: set FHIR_* + PORTAL_JWT_* env vars, then open
/portal/dashboard?patient_id=<Epic sandbox patient id>.
"""

from flask import Blueprint, render_template, request

from fhir import get_fhir_client
from fhir.jwks import public_jwks_uri

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


@portal_bp.route("/")
@portal_bp.route("/dashboard")
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
