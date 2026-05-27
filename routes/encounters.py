from datetime import datetime

from auth import employee_required
from config import SERVICE_LABELS
from forms import EncounterForm, EncounterSearchForm, NoteForm, empty_select
from models import (
    Advocate,
    Encounter,
    HomeHealthFacility,
    Hospital,
    Note,
    Patient,
    Provider,
    db,
)
from flask import Blueprint, flash, redirect, render_template, request, url_for

encounters_bp = Blueprint("encounters", __name__, url_prefix="/encounters")


def _parse_datetime(value):
    if not value or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _populate_encounter_form(form, encounter=None):
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    advocates = Advocate.query.filter_by(active=True).order_by(Advocate.name).all()
    providers = Provider.query.order_by(Provider.name).all()
    hospitals = Hospital.query.order_by(Hospital.name).all()
    facilities = HomeHealthFacility.query.order_by(HomeHealthFacility.name).all()

    form.patient_id.choices = empty_select("patient") + [
        (p.id, p.full_name) for p in patients
    ]
    form.advocate_id.choices = [(0, "None")] + [(a.id, a.name) for a in advocates]
    form.provider_id.choices = [(0, "None")] + [(p.id, p.name) for p in providers]
    form.hospital_id.choices = [(0, "None")] + [(h.id, h.name) for h in hospitals]
    form.home_health_facility_id.choices = [(0, "None")] + [
        (f.id, f.name) for f in facilities
    ]

    if encounter:
        form.patient_id.data = encounter.patient_id
        form.advocate_id.data = encounter.advocate_id or 0
        form.provider_id.data = encounter.provider_id or 0
        form.hospital_id.data = encounter.hospital_id or 0
        form.home_health_facility_id.data = encounter.home_health_facility_id or 0
        form.encounter_type.data = encounter.encounter_type
        form.status.data = encounter.status
        form.scheduled_at.data = (
            encounter.scheduled_at.isoformat(timespec="minutes")
            if encounter.scheduled_at
            else ""
        )
        form.started_at.data = (
            encounter.started_at.isoformat(timespec="minutes")
            if encounter.started_at
            else ""
        )
        form.ended_at.data = (
            encounter.ended_at.isoformat(timespec="minutes") if encounter.ended_at else ""
        )


def _save_encounter_from_form(form, encounter=None):
    encounter = encounter or Encounter()
    encounter.patient_id = form.patient_id.data
    encounter.advocate_id = form.advocate_id.data
    encounter.provider_id = form.provider_id.data
    encounter.hospital_id = form.hospital_id.data
    encounter.home_health_facility_id = form.home_health_facility_id.data
    encounter.encounter_type = form.encounter_type.data
    encounter.status = form.status.data
    encounter.scheduled_at = _parse_datetime(form.scheduled_at.data)
    encounter.started_at = _parse_datetime(form.started_at.data)
    encounter.ended_at = _parse_datetime(form.ended_at.data)
    if not encounter.id:
        db.session.add(encounter)
    db.session.commit()
    return encounter


@encounters_bp.route("/")
@employee_required
def list_encounters():
    search_form = EncounterSearchForm(formdata=request.args)
    query = Encounter.query.join(Patient)

    if search_form.q.data:
        term = f"%{search_form.q.data.strip()}%"
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
            )
        )
    if search_form.status.data:
        query = query.filter(Encounter.status == search_form.status.data)
    if search_form.encounter_type.data:
        query = query.filter(Encounter.encounter_type == search_form.encounter_type.data)

    encounters = query.order_by(Encounter.created_at.desc()).all()
    return render_template(
        "staff/encounters/list.html",
        encounters=encounters,
        search_form=search_form,
        service_labels=SERVICE_LABELS,
    )


@encounters_bp.route("/new", methods=["GET", "POST"])
@employee_required
def new_encounter():
    form = EncounterForm()
    _populate_encounter_form(form)
    if form.validate_on_submit():
        encounter = _save_encounter_from_form(form)
        flash("Encounter created successfully.", "success")
        return redirect(url_for("encounters.view_encounter", encounter_id=encounter.id))
    return render_template("staff/encounters/form.html", form=form, title="New Encounter")


@encounters_bp.route("/<int:encounter_id>")
@employee_required
def view_encounter(encounter_id):
    encounter = Encounter.query.get_or_404(encounter_id)
    notes = encounter.notes.order_by(Note.created_at.desc()).all()
    return render_template(
        "staff/encounters/detail.html",
        encounter=encounter,
        notes=notes,
        service_labels=SERVICE_LABELS,
    )


@encounters_bp.route("/<int:encounter_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_encounter(encounter_id):
    encounter = Encounter.query.get_or_404(encounter_id)
    form = EncounterForm(obj=encounter)
    _populate_encounter_form(form, encounter)
    if form.validate_on_submit():
        _save_encounter_from_form(form, encounter)
        flash("Encounter updated successfully.", "success")
        return redirect(url_for("encounters.view_encounter", encounter_id=encounter.id))
    return render_template(
        "staff/encounters/form.html",
        form=form,
        title=f"Edit Encounter #{encounter.id}",
        encounter=encounter,
    )


@encounters_bp.route("/<int:encounter_id>/notes/new", methods=["GET", "POST"])
@employee_required
def new_note(encounter_id):
    encounter = Encounter.query.get_or_404(encounter_id)
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(
            encounter_id=encounter.id,
            content=form.content.data.strip(),
            author=(form.author.data or "").strip() or None,
        )
        db.session.add(note)
        db.session.commit()
        flash("Note added successfully.", "success")
        return redirect(url_for("encounters.view_encounter", encounter_id=encounter.id))
    return render_template(
        "staff/encounters/note_form.html",
        form=form,
        encounter=encounter,
    )
