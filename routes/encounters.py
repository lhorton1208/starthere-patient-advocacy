from datetime import datetime, timezone

from auth import employee_required
from config import SERVICE_LABELS
from forms import (
    EncounterForm,
    EncounterSearchForm,
    NoteForm,
    VisitNoteForm,
    empty_select,
)
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
from sqlalchemy.exc import IntegrityError

encounters_bp = Blueprint("encounters", __name__, url_prefix="/encounters")


def _parse_datetime(value):
    if not value or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def _utcnow():
    return datetime.now(timezone.utc)


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


def _choice_ids(choices):
    return {choice[0] for choice in choices}


def _append_choice(choices, value, label):
    if value and value not in _choice_ids(choices):
        choices.append((value, label))


def _populate_visit_note_form(form, note=None):
    visits = Encounter.query.join(
        Patient, Encounter.patient_id == Patient.id
    ).order_by(Encounter.id.desc()).all()
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    advocates = Advocate.query.order_by(Advocate.name).all()

    form.visit_number.choices = [(0, "Select visit...")] + [
        (v.id, f"Visit #{v.id} — {v.patient.full_name}") for v in visits
    ]
    form.patient_id.choices = empty_select("patient") + [
        (p.id, f"{p.id} — {p.full_name}") for p in patients
    ]
    form.advocate_id.choices = [(0, "Select advocate...")] + [
        (a.id, a.name) for a in advocates
    ]

    if note:
        if note.encounter_id:
            _append_choice(
                form.visit_number.choices,
                note.encounter_id,
                f"Visit #{note.encounter_id}",
            )
        if note.patient_id:
            patient = note.patient or Patient.query.get(note.patient_id)
            label = (
                f"{note.patient_id} — {patient.full_name}"
                if patient
                else f"{note.patient_id} — (removed)"
            )
            _append_choice(form.patient_id.choices, note.patient_id, label)
        if note.advocate_id:
            advocate = note.advocate or Advocate.query.get(note.advocate_id)
            label = advocate.name if advocate else f"Advocate #{note.advocate_id}"
            _append_choice(form.advocate_id.choices, note.advocate_id, label)

        form.visit_number.data = note.encounter_id or 0
        form.patient_id.data = note.patient_id
        form.advocate_id.data = note.advocate_id or 0
        form.internal_only.data = note.internal_only
        form.description.data = note.description
        form.note_text.data = note.note_text or note.content


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


def _save_visit_note_from_form(form, note=None):
    note = note or Note()
    visit_id = form.visit_number.data
    note.encounter_id = visit_id if visit_id else None
    note.patient_id = form.patient_id.data
    note.advocate_id = form.advocate_id.data or None
    note.internal_only = bool(form.internal_only.data)
    note.description = (form.description.data or "").strip() or None
    body = form.note_text.data.strip()
    note.note_text = body
    note.content = body
    if not note.note_datetime:
        note.note_datetime = _utcnow()
    if visit_id and not note.patient_id:
        visit = Encounter.query.get(visit_id)
        if visit:
            note.patient_id = visit.patient_id
    if not note.id:
        db.session.add(note)
    db.session.commit()
    return note


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
        flash("Visit created successfully.", "success")
        return redirect(url_for("encounters.view_encounter", encounter_id=encounter.id))
    return render_template("staff/encounters/form.html", form=form, title="New Visit")


@encounters_bp.route("/notes", strict_slashes=False)
@employee_required
def list_notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template("staff/encounters/notes_list.html", notes=notes)


@encounters_bp.route("/notes/new", methods=["GET", "POST"], strict_slashes=False)
@employee_required
def new_visit_note():
    form = VisitNoteForm()
    _populate_visit_note_form(form)
    preselect_visit = request.args.get("visit_number", type=int)
    preselect_patient = request.args.get("patient_id", type=int)
    if preselect_visit:
        form.visit_number.data = preselect_visit
    if preselect_patient:
        form.patient_id.data = preselect_patient

    if form.validate_on_submit():
        try:
            note = _save_visit_note_from_form(form)
        except IntegrityError:
            db.session.rollback()
            flash(
                "Could not save the note. Check that the patient and visit are valid.",
                "error",
            )
        else:
            flash("Note saved successfully.", "success")
            return redirect(url_for("encounters.edit_visit_note", note_id=note.id))
    return render_template(
        "staff/encounters/note_record_form.html",
        form=form,
        note=None,
        title="New Note",
    )


@encounters_bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"], strict_slashes=False)
@employee_required
def edit_visit_note(note_id):
    note = Note.query.get_or_404(note_id)
    form = VisitNoteForm(obj=note)
    _populate_visit_note_form(form, note)

    if form.validate_on_submit():
        try:
            _save_visit_note_from_form(form, note)
        except IntegrityError:
            db.session.rollback()
            flash(
                "Could not update the note. Check that the patient and visit are valid.",
                "error",
            )
        else:
            flash("Note updated successfully.", "success")
            return redirect(url_for("encounters.edit_visit_note", note_id=note.id))
    return render_template(
        "staff/encounters/note_record_form.html",
        form=form,
        note=note,
        title=f"Edit Note #{note.id}",
    )


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
        flash("Visit updated successfully.", "success")
        return redirect(url_for("encounters.view_encounter", encounter_id=encounter.id))
    return render_template(
        "staff/encounters/form.html",
        form=form,
        title=f"Edit Visit #{encounter.id}",
        encounter=encounter,
    )


@encounters_bp.route("/<int:encounter_id>/notes/new", methods=["GET", "POST"])
@employee_required
def new_note(encounter_id):
    encounter = Encounter.query.get_or_404(encounter_id)
    form = NoteForm()
    if form.validate_on_submit():
        body = form.content.data.strip()
        note = Note(
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            advocate_id=encounter.advocate_id,
            content=body,
            note_text=body,
            author=(form.author.data or "").strip() or None,
            note_datetime=_utcnow(),
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
