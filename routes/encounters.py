from datetime import datetime, timezone

from auth import employee_required
from config import SERVICE_LABELS
from forms import (
    EncounterForm,
    EncounterSearchForm,
    NoteForm,
    TimeCardForm,
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
    TimeCard,
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


def _choice_ids(choices):
    return {choice[0] for choice in choices}


def _append_choice(choices, value, label):
    if value is not None and value not in _choice_ids(choices):
        choices.append((value, label))


def _advocate_choice_label(advocate_id):
    advocate = Advocate.query.get(advocate_id)
    if advocate:
        suffix = "" if advocate.active else " (inactive)"
        return f"{advocate.name}{suffix}"
    return f"Advocate #{advocate_id}"


def _ensure_advocate_in_choices(form, advocate_id):
    if advocate_id:
        _append_choice(
            form.advocate_id.choices,
            advocate_id,
            _advocate_choice_label(advocate_id),
        )


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
        _ensure_advocate_in_choices(form, encounter.advocate_id)
        if not form.is_submitted():
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
        else:
            _ensure_advocate_in_choices(form, form.advocate_id.data)


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
        (a.id, f"{a.name}{'' if a.active else ' (inactive)'}") for a in advocates
    ]

    visit_id = form.visit_number.data if form.is_submitted() else None
    if note and not form.is_submitted():
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
        _ensure_advocate_in_choices(form, note.advocate_id)

        form.visit_number.data = note.encounter_id or 0
        form.patient_id.data = note.patient_id
        form.advocate_id.data = note.advocate_id or 0
        form.internal_only.data = note.internal_only
        form.description.data = note.description
        form.note_text.data = note.note_text or note.content
        visit_id = note.encounter_id or visit_id

    if visit_id:
        visit = Encounter.query.get(visit_id)
        if visit and visit.advocate_id:
            _ensure_advocate_in_choices(form, visit.advocate_id)

    if form.is_submitted():
        _ensure_advocate_in_choices(form, form.advocate_id.data)


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


def _visit_choice_label(visit):
    return f"Visit #{visit.id} — {visit.patient.full_name}"


def _populate_time_card_form(form, time_card=None):
    visits = Encounter.query.join(
        Patient, Encounter.patient_id == Patient.id
    ).order_by(Encounter.id.desc()).all()
    advocates = Advocate.query.order_by(Advocate.name).all()

    form.encounter_id.choices = empty_select("visit") + [
        (v.id, _visit_choice_label(v)) for v in visits
    ]
    form.advocate_id.choices = empty_select("advocate") + [
        (a.id, f"{a.name}{'' if a.active else ' (inactive)'}") for a in advocates
    ]

    if time_card and not form.is_submitted():
        if time_card.encounter_id:
            _append_choice(
                form.encounter_id.choices,
                time_card.encounter_id,
                f"Visit #{time_card.encounter_id}",
            )
        _ensure_advocate_in_choices(form, time_card.advocate_id)

        form.advocate_id.data = time_card.advocate_id
        form.encounter_id.data = time_card.encounter_id
        form.work_date.data = time_card.work_date
        form.hours.data = time_card.hours
        form.description.data = time_card.description

    visit_id = form.encounter_id.data if form.is_submitted() else None
    if not visit_id and time_card and not form.is_submitted():
        visit_id = time_card.encounter_id

    if visit_id:
        visit = Encounter.query.get(visit_id)
        if visit:
            _append_choice(form.encounter_id.choices, visit.id, _visit_choice_label(visit))
            if visit.advocate_id and not form.is_submitted():
                _ensure_advocate_in_choices(form, visit.advocate_id)
                if not time_card:
                    form.advocate_id.data = visit.advocate_id

    if form.is_submitted():
        _ensure_advocate_in_choices(form, form.advocate_id.data)
        if form.encounter_id.data:
            _append_choice(
                form.encounter_id.choices,
                form.encounter_id.data,
                f"Visit #{form.encounter_id.data}",
            )


def _save_time_card_from_form(form, time_card=None):
    time_card = time_card or TimeCard()
    time_card.advocate_id = form.advocate_id.data
    time_card.encounter_id = form.encounter_id.data
    time_card.work_date = form.work_date.data
    time_card.hours = form.hours.data
    time_card.description = (form.description.data or "").strip() or None
    if not time_card.id:
        db.session.add(time_card)
    db.session.commit()
    return time_card


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
    preselect_visit = request.args.get("visit_number", type=int)
    preselect_patient = request.args.get("patient_id", type=int)
    if not form.is_submitted():
        if preselect_visit:
            form.visit_number.data = preselect_visit
        if preselect_patient:
            form.patient_id.data = preselect_patient
        if preselect_visit:
            visit = Encounter.query.get(preselect_visit)
            if visit:
                if visit.advocate_id and not form.advocate_id.data:
                    form.advocate_id.data = visit.advocate_id
                if visit.patient_id and not preselect_patient:
                    form.patient_id.data = visit.patient_id
    _populate_visit_note_form(form)

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


@encounters_bp.route("/time-cards", strict_slashes=False)
@employee_required
def list_time_cards():
    time_cards = (
        TimeCard.query.join(Advocate)
        .order_by(TimeCard.work_date.desc(), TimeCard.id.desc())
        .all()
    )
    return render_template("staff/encounters/time_cards_list.html", time_cards=time_cards)


@encounters_bp.route("/time-cards/new", methods=["GET", "POST"], strict_slashes=False)
@employee_required
def new_time_card():
    form = TimeCardForm()
    preselect_visit = request.args.get("encounter_id", type=int)
    if not form.is_submitted() and preselect_visit:
        form.encounter_id.data = preselect_visit
        visit = Encounter.query.get(preselect_visit)
        if visit and visit.advocate_id:
            form.advocate_id.data = visit.advocate_id
    _populate_time_card_form(form)

    if form.validate_on_submit():
        try:
            time_card = _save_time_card_from_form(form)
        except IntegrityError:
            db.session.rollback()
            flash(
                "Could not save the time card. Check that the advocate and visit are valid.",
                "error",
            )
        else:
            flash("Time card saved successfully.", "success")
            return redirect(
                url_for("encounters.edit_time_card", time_card_id=time_card.id)
            )
    return render_template(
        "staff/encounters/time_card_form.html",
        form=form,
        time_card=None,
        title="New Time Card",
    )


@encounters_bp.route(
    "/time-cards/<int:time_card_id>/edit", methods=["GET", "POST"], strict_slashes=False
)
@employee_required
def edit_time_card(time_card_id):
    time_card = TimeCard.query.get_or_404(time_card_id)
    form = TimeCardForm(obj=time_card)
    _populate_time_card_form(form, time_card)

    if form.validate_on_submit():
        try:
            _save_time_card_from_form(form, time_card)
        except IntegrityError:
            db.session.rollback()
            flash(
                "Could not update the time card. Check that the advocate and visit are valid.",
                "error",
            )
        else:
            flash("Time card updated successfully.", "success")
            return redirect(
                url_for("encounters.edit_time_card", time_card_id=time_card.id)
            )
    return render_template(
        "staff/encounters/time_card_form.html",
        form=form,
        time_card=time_card,
        title=f"Edit Time Card #{time_card.id}",
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
