import re

from auth import employee_required
from config import SERVICE_LABELS
from forms import AdHocQueryForm
from models import Advocate, Client, Encounter, Patient, TimeCard, db
from flask import Blueprint, flash, render_template
from sqlalchemy import text

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


def _validate_select_only(sql: str):
    cleaned = sql.strip().rstrip(";")
    if not cleaned.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    if FORBIDDEN_SQL.search(cleaned):
        raise ValueError("Query contains forbidden SQL keywords.")
    if ";" in cleaned:
        raise ValueError("Multiple statements are not allowed.")
    return cleaned


@reports_bp.route("/encounters")
@employee_required
def report_encounters():
    rows = (
        Encounter.query.join(Patient)
        .order_by(Encounter.created_at.desc())
        .all()
    )
    return render_template(
        "staff/reports/encounters.html",
        rows=rows,
        service_labels=SERVICE_LABELS,
        title="Encounters Report",
    )


@reports_bp.route("/patients")
@employee_required
def report_patients():
    rows = (
        Patient.query.join(Client, Patient.client_id == Client.id)
        .order_by(Patient.last_name, Patient.first_name)
        .all()
    )
    return render_template(
        "staff/reports/patients.html",
        rows=rows,
        title="Patients Report",
    )


@reports_bp.route("/advocates")
@employee_required
def report_advocates():
    rows = Advocate.query.order_by(Advocate.name).all()
    return render_template(
        "staff/reports/advocates.html",
        rows=rows,
        title="Advocates Report",
    )


@reports_bp.route("/time-cards")
@employee_required
def report_time_cards():
    rows = (
        TimeCard.query.join(Advocate)
        .order_by(TimeCard.work_date.desc(), Advocate.name)
        .all()
    )
    return render_template(
        "staff/reports/time_cards.html",
        rows=rows,
        title="Time Cards Report",
    )


@reports_bp.route("/ad-hoc", methods=["GET", "POST"])
@employee_required
def report_ad_hoc():
    form = AdHocQueryForm()
    columns = []
    results = []
    error = None

    if form.validate_on_submit():
        try:
            query = _validate_select_only(form.sql.data)
            result = db.session.execute(text(query))
            columns = list(result.keys())
            results = [dict(row._mapping) for row in result.fetchmany(200)]
            if not results:
                flash("Query ran successfully but returned no rows.", "success")
        except ValueError as exc:
            error = str(exc)
            flash(error, "error")
        except Exception as exc:
            error = str(exc)
            flash(f"Query failed: {error}", "error")

    return render_template(
        "staff/reports/ad_hoc.html",
        form=form,
        columns=columns,
        results=results,
        error=error,
        title="Ad-Hoc SQL Queries",
    )
