import re
from datetime import datetime, time

from auth import employee_required
from config import SERVICE_LABELS
from forms import AdHocQueryForm, NotesReportForm
from models import Advocate, Client, Encounter, Note, Patient, TimeCard, db
from flask import Blueprint, flash, render_template, request
from sqlalchemy import func, text

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


def _populate_notes_report_form(form):
    visits = (
        Encounter.query.join(Patient, Encounter.patient_id == Patient.id)
        .order_by(Encounter.id.desc())
        .all()
    )
    form.visit_id.choices = [(0, "All visits")] + [
        (v.id, f"Visit #{v.id} — {v.patient.full_name}") for v in visits
    ]

    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    form.patient_id.choices = [(0, "All patients")] + [
        (p.id, f"{p.id} — {p.full_name}") for p in patients
    ]

    advocates = Advocate.query.order_by(Advocate.name).all()
    form.advocate_id.choices = [(0, "All advocates")] + [
        (a.id, f"{a.id} — {a.name}") for a in advocates
    ]

    for field in (form.visit_id, form.patient_id, form.advocate_id):
        valid_ids = {choice[0] for choice in field.choices}
        if field.data not in valid_ids:
            field.data = 0


def _notes_report_rows(form):
    timestamp = func.coalesce(Note.note_datetime, Note.created_at)
    query = Note.query.outerjoin(Advocate, Note.advocate_id == Advocate.id)

    if form.visit_id.data:
        query = query.filter(Note.encounter_id == form.visit_id.data)
    if form.patient_id.data:
        query = query.filter(Note.patient_id == form.patient_id.data)
    if form.advocate_id.data:
        query = query.filter(Note.advocate_id == form.advocate_id.data)

    advocate_name = (form.advocate_name.data or "").strip()
    if advocate_name:
        query = query.filter(Advocate.name.ilike(f"%{advocate_name}%"))

    if form.date_from.data:
        start = datetime.combine(form.date_from.data, time.min)
        query = query.filter(timestamp >= start)
    if form.date_to.data:
        end = datetime.combine(form.date_to.data, time.max)
        query = query.filter(timestamp <= end)

    internal_filter = form.internal_only.data or "all"
    if internal_filter == "exclude":
        query = query.filter(Note.internal_only.is_(False))
    elif internal_filter == "only":
        query = query.filter(Note.internal_only.is_(True))

    if form.sort.data == "asc":
        query = query.order_by(timestamp.asc(), Note.id.asc())
    else:
        query = query.order_by(timestamp.desc(), Note.id.desc())

    return query.all()


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
        title="Visits Report",
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


@reports_bp.route("/notes")
@employee_required
def report_notes():
    form = NotesReportForm(formdata=request.args)
    _populate_notes_report_form(form)
    rows = _notes_report_rows(form)
    return render_template(
        "staff/reports/notes.html",
        form=form,
        rows=rows,
        title="Notes Report",
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
