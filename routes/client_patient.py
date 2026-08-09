from auth import employee_required
from forms import (
    ClientInfoForm,
    DeletePatientForm,
    ErVisitForm,
    OutpatientProcedureForm,
    PatientInfoForm,
    PatientRecordForm,
    empty_select,
)
from intake import (
    LOOKUP_FOUND,
    create_intake_request,
    ensure_client_and_patient,
    format_er_visit_notes,
    format_outpatient_procedure_notes,
    get_patient_by_id,
    normalize_email,
    resolve_patient_lookup,
)
from models import (
    Client,
    Company,
    Patient,
    Provider,
    RelationshipToPatient,
    db,
    delete_patient_record,
    link_client_patient,
)
from datetime import date
from typing import Optional

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from seed import COMPANY_NAME
from sqlalchemy.exc import IntegrityError

client_patient_bp = Blueprint("client_patient", __name__, url_prefix="/client")

PATIENT_DRAFT_SESSION_KEY = "patient_form_draft"
NEW_CLIENT_OPTION = -1
NEW_PROVIDER_OPTION = -1


def _parse_hidden_patient_id(form) -> Optional[int]:
    raw = (getattr(form, "patient_id", None) and form.patient_id.data) or ""
    raw = str(raw).strip()
    if raw.isdigit():
        return int(raw)
    return None


def _prefill_service_intake_form(form) -> None:
    """Prefill dedicated service forms from Service Request handoff query params."""
    if request.method != "GET":
        return

    patient = None
    pid = request.args.get("patient_id", type=int)
    if pid:
        patient = get_patient_by_id(pid)

    if patient:
        form.patient_id.data = str(patient.id)
        form.patient_name.data = f"{patient.full_name} (ID {patient.id})"
    else:
        patient_name = (request.args.get("patient_name") or "").strip()
        if patient_name and not form.patient_name.data:
            form.patient_name.data = patient_name

    for field_name in ("contact_name", "phone", "email"):
        value = (request.args.get(field_name) or "").strip()
        field = getattr(form, field_name, None)
        if field is not None and value and not field.data:
            field.data = value


def _company():
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        raise RuntimeError("StartHere company record is missing.")
    return company


def _provider_choices():
    providers = Provider.query.order_by(
        Provider.last_name, Provider.first_name, Provider.name
    ).all()
    return (
        [(0, "None")]
        + [(NEW_PROVIDER_OPTION, "+ Add new provider...")]
        + [(p.id, p.choice_label) for p in providers]
    )


def _strip(value):
    return (value or "").strip() or None


def _populate_client_form(form, client=None):
    relationships = RelationshipToPatient.query.order_by(
        RelationshipToPatient.relationship
    ).all()
    form.relationship_to_patient_id.choices = [(0, "Select relationship...")] + [
        (r.id, r.relationship) for r in relationships
    ]
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    form.patient_id.choices = [(0, "None")] + [
        (p.id, p.full_name) for p in patients
    ]
    if client:
        if not client.first_name and client.name:
            client.sync_name_fields()
        if client.patients.count():
            form.patient_id.data = client.patients.first().id
        if client.relationship_to_patient_id:
            form.relationship_to_patient_id.data = client.relationship_to_patient_id


def _populate_patient_form(form, patient=None):
    clients = Client.query.order_by(Client.last_name, Client.first_name, Client.name).all()
    form.client_id.choices = (
        empty_select("client")
        + [(NEW_CLIENT_OPTION, "+ Add new client...")]
        + [(c.id, c.display_name) for c in clients]
    )
    form.primary_provider_id.choices = _provider_choices()
    if patient:
        form.client_id.data = patient.client_id
        if not patient.phone_mobile and patient.phone:
            form.phone_mobile.data = patient.phone
        if not form.is_submitted():
            form.primary_provider_id.data = patient.primary_provider_id or 0


def _patient_draft_from_form(form, patient_id=None):
    dob = form.date_of_birth.data
    return {
        "patient_id": patient_id,
        "client_id": form.client_id.data,
        "primary_provider_id": form.primary_provider_id.data,
        "prefix": form.prefix.data or "",
        "first_name": form.first_name.data or "",
        "middle_name": form.middle_name.data or "",
        "last_name": form.last_name.data or "",
        "suffix": form.suffix.data or "",
        "date_of_birth": dob.isoformat() if dob else "",
        "last4_ssn": form.last4_ssn.data or "",
        "phone_mobile": form.phone_mobile.data or "",
        "phone_landline": form.phone_landline.data or "",
        "email": form.email.data or "",
        "address": form.address.data or "",
        "city": form.city.data or "",
        "state": form.state.data or "",
        "zip_code": form.zip_code.data or "",
        "mood": form.mood.data or "",
        "mental_state": form.mental_state.data or "",
        "intake_notes": form.intake_notes.data or "",
    }


def _apply_patient_draft_to_form(form, draft):
    form.prefix.data = draft.get("prefix") or None
    form.first_name.data = draft.get("first_name") or ""
    form.middle_name.data = draft.get("middle_name") or None
    form.last_name.data = draft.get("last_name") or ""
    form.suffix.data = draft.get("suffix") or None
    dob = draft.get("date_of_birth") or ""
    if dob:
        try:
            form.date_of_birth.data = date.fromisoformat(dob)
        except ValueError:
            form.date_of_birth.data = None
    form.last4_ssn.data = draft.get("last4_ssn") or None
    form.phone_mobile.data = draft.get("phone_mobile") or None
    form.phone_landline.data = draft.get("phone_landline") or None
    form.email.data = draft.get("email") or None
    form.address.data = draft.get("address") or None
    form.city.data = draft.get("city") or None
    form.state.data = draft.get("state") or None
    form.zip_code.data = draft.get("zip_code") or None
    form.mood.data = draft.get("mood") or None
    form.mental_state.data = draft.get("mental_state") or None
    form.intake_notes.data = draft.get("intake_notes") or None
    client_id = draft.get("client_id")
    if client_id and client_id > 0:
        form.client_id.data = client_id
    provider_id = draft.get("primary_provider_id")
    if provider_id and provider_id > 0:
        form.primary_provider_id.data = provider_id
    elif provider_id == 0 or provider_id is None:
        form.primary_provider_id.data = 0


def _save_patient_draft(form, patient_id=None):
    session[PATIENT_DRAFT_SESSION_KEY] = _patient_draft_from_form(form, patient_id)
    session.modified = True


def _patient_resume_url(draft):
    patient_id = draft.get("patient_id")
    if patient_id:
        return url_for("client_patient.edit_patient", patient_id=patient_id)
    return url_for("client_patient.edit_patient")


def _apply_client_from_form(record, form):
    record.prefix = _strip(form.prefix.data)
    record.first_name = form.first_name.data.strip()
    record.middle_name = _strip(form.middle_name.data)
    record.last_name = form.last_name.data.strip()
    record.suffix = _strip(form.suffix.data)
    record.account_number = _strip(form.account_number.data)
    record.phone = _strip(form.phone.data)
    record.phone_number2 = _strip(form.phone_number2.data)
    record.email = normalize_email(form.email.data)
    rel_id = form.relationship_to_patient_id.data
    record.relationship_to_patient_id = rel_id if rel_id else None
    record.address = _strip(form.address.data)
    record.city = _strip(form.city.data)
    record.state = _strip(form.state.data)
    record.zip_code = _strip(form.zip_code.data)
    record.sync_name_fields()


def _apply_patient_from_form(record, form):
    record.prefix = _strip(form.prefix.data)
    record.first_name = form.first_name.data.strip()
    record.middle_name = _strip(form.middle_name.data)
    record.last_name = form.last_name.data.strip()
    record.suffix = _strip(form.suffix.data)
    record.date_of_birth = form.date_of_birth.data
    ssn = _strip(form.last4_ssn.data)
    if ssn and len(ssn) != 4:
        raise ValueError("Last 4 of SSN must be exactly 4 characters.")
    record.last4_ssn = ssn if ssn else None
    record.phone_mobile = _strip(form.phone_mobile.data)
    record.phone_landline = _strip(form.phone_landline.data)
    record.phone = record.phone_mobile or record.phone_landline
    record.email = normalize_email(form.email.data)
    record.address = _strip(form.address.data)
    record.city = _strip(form.city.data)
    record.state = _strip(form.state.data)
    record.zip_code = _strip(form.zip_code.data)
    record.mood = _strip(form.mood.data)
    record.mental_state = _strip(form.mental_state.data)
    record.intake_notes = _strip(form.intake_notes.data)
    provider_id = form.primary_provider_id.data
    record.primary_provider_id = provider_id if provider_id and provider_id > 0 else None


@client_patient_bp.route("/client-info")
@employee_required
def list_clients():
    from audit import log_phi_list

    rows = Client.query.order_by(Client.last_name, Client.first_name, Client.name).all()
    log_phi_list("clients", row_count=len(rows))
    return render_template("client/client_list.html", rows=rows)


@client_patient_bp.route("/client-info/new", methods=["GET", "POST"])
@client_patient_bp.route("/client-info/<int:client_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_client(client_id=None):
    from audit import log_phi_select

    company = _company()
    client = Client.query.get(client_id) if client_id else None
    if client and request.method == "GET":
        log_phi_select(
            "clients",
            record_id=client.id,
            client_id=client.id,
            patient_id=client.patient_id,
            detail="edit form loaded",
        )
    form = ClientInfoForm(obj=client)
    _populate_client_form(form, client)

    if form.validate_on_submit():
        record = client or Client(company_id=company.id)
        _apply_client_from_form(record, form)
        if not client:
            db.session.add(record)
            db.session.flush()

        if form.patient_id.data:
            patient = Patient.query.get(form.patient_id.data)
            if patient:
                if patient.client_id != record.id and Patient.query.filter_by(
                    client_id=record.id
                ).first():
                    flash("This client is already linked to another patient.", "error")
                    return render_template(
                        "client/client_form.html",
                        form=form,
                        client=client,
                        title="Edit Client" if client else "New Client",
                    )
                link_client_patient(record, patient)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A client with this email already exists.", "error")
            return render_template(
                "client/client_form.html",
                form=form,
                client=client,
                title="Edit Client" if client else "New Client",
            )
        flash("Client saved.", "success")
        draft = session.get(PATIENT_DRAFT_SESSION_KEY)
        resume_patient = request.args.get("resume_patient") or request.form.get(
            "resume_patient"
        )
        if resume_patient and draft is not None:
            draft["client_id"] = record.id
            session[PATIENT_DRAFT_SESSION_KEY] = draft
            session.modified = True
            flash("Client saved. Your patient entries have been restored.", "success")
            return redirect(_patient_resume_url(draft))

        return redirect(url_for("client_patient.view_client", client_id=record.id))

    resume_patient = request.args.get("resume_patient")
    cancel_url = None
    if resume_patient and session.get(PATIENT_DRAFT_SESSION_KEY):
        cancel_url = _patient_resume_url(session[PATIENT_DRAFT_SESSION_KEY])

    return render_template(
        "client/client_form.html",
        form=form,
        client=client,
        resume_patient=bool(resume_patient),
        cancel_url=cancel_url,
        title="Edit Client" if client else "New Client",
    )


@client_patient_bp.route("/client-info/<int:client_id>")
@employee_required
def view_client(client_id):
    from audit import log_phi_select

    client = Client.query.get_or_404(client_id)
    patients = client.patients.order_by(Patient.last_name).all()
    log_phi_select(
        "clients",
        record_id=client.id,
        client_id=client.id,
        patient_id=client.patient_id,
        detail="client detail viewed",
    )
    if patients:
        from audit import log_phi_list

        log_phi_list(
            "patients",
            row_count=len(patients),
            detail=f"patients listed for client_id={client.id}",
        )
    return render_template("client/client_detail.html", client=client, patients=patients)


@client_patient_bp.route("/patient-info")
@employee_required
def list_patients():
    from audit import log_phi_list

    rows = (
        Patient.query.join(Client, Patient.client_id == Client.id)
        .order_by(Patient.last_name, Patient.first_name)
        .all()
    )
    log_phi_list("patients", row_count=len(rows))
    return render_template("client/patient_list.html", rows=rows)


@client_patient_bp.route("/patient-info/new", methods=["GET", "POST"])
@client_patient_bp.route("/patient-info/<int:patient_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_patient(patient_id=None):
    from audit import log_phi_select

    company = _company()
    patient = Patient.query.get(patient_id) if patient_id else None
    if patient and request.method == "GET":
        log_phi_select(
            "patients",
            record_id=patient.id,
            patient_id=patient.id,
            client_id=patient.client_id,
            detail="edit form loaded",
        )
    if request.method == "POST":
        form = PatientRecordForm(formdata=request.form, obj=patient)
    else:
        form = PatientRecordForm(obj=patient)
    delete_form = DeletePatientForm()
    _populate_patient_form(form, patient)

    if request.method == "POST" and request.form.get("action") == "add_client":
        _save_patient_draft(form, patient_id)
        return redirect(url_for("client_patient.edit_client", resume_patient=1))

    if request.method == "POST" and request.form.get("action") == "add_provider":
        _save_patient_draft(form, patient_id)
        return redirect(url_for("entities.edit_provider", resume_patient=1))

    draft = session.get(PATIENT_DRAFT_SESSION_KEY)
    if draft and (draft.get("patient_id") == patient_id or (not patient_id and not draft.get("patient_id"))):
        _apply_patient_draft_to_form(form, draft)

    preselect_client = request.args.get("client_id", type=int)
    if preselect_client and preselect_client > 0:
        form.client_id.data = preselect_client

    if form.validate_on_submit() and request.form.get("action", "save") == "save":
        if form.client_id.data == NEW_CLIENT_OPTION:
            flash("Select a client or use Add New Client to create one.", "error")
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )

        if form.primary_provider_id.data == NEW_PROVIDER_OPTION:
            flash(
                "Select a primary care provider or use Add New Provider to create one.",
                "error",
            )
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )

        client = Client.query.get(form.client_id.data)
        if not client:
            flash("Please select a valid client.", "error")
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )

        other = Patient.query.filter(
            Patient.client_id == client.id,
            Patient.id != (patient.id if patient else -1),
        ).first()
        if other:
            flash("This client is already linked to another patient.", "error")
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )

        record = patient or Patient(company_id=company.id, client_id=client.id)
        record.client_id = client.id
        try:
            _apply_patient_from_form(record, form)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )
        if not patient:
            db.session.add(record)
            db.session.flush()
        link_client_patient(client, record)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A patient with this email already exists.", "error")
            return render_template(
                "client/patient_form.html",
                form=form,
                delete_form=delete_form,
                patient=patient,
                title="Edit Patient" if patient else "New Patient",
            )
        session.pop(PATIENT_DRAFT_SESSION_KEY, None)
        flash("Patient saved.", "success")
        return redirect(url_for("client_patient.view_patient", patient_id=record.id))

    return render_template(
        "client/patient_form.html",
        form=form,
        delete_form=delete_form,
        patient=patient,
        title="Edit Patient" if patient else "New Patient",
    )


@client_patient_bp.route("/patient-info/<int:patient_id>/delete", methods=["POST"])
@employee_required
def delete_patient(patient_id):
    form = DeletePatientForm()
    if not form.validate_on_submit():
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("client_patient.edit_patient", patient_id=patient_id))

    patient = Patient.query.get_or_404(patient_id)
    name = patient.full_name
    delete_patient_record(patient)
    db.session.commit()
    flash(f"Patient {name} has been removed.", "success")
    return redirect(url_for("client_patient.list_patients"))


@client_patient_bp.route("/patient-info/<int:patient_id>")
@employee_required
def view_patient(patient_id):
    from audit import log_phi_list, log_phi_select
    from config import SERVICE_LABELS
    from models import Encounter, Note

    patient = Patient.query.get_or_404(patient_id)
    log_phi_select(
        "patients",
        record_id=patient.id,
        patient_id=patient.id,
        client_id=patient.client_id,
        detail="patient detail viewed",
    )

    encounters = (
        Encounter.query.filter_by(patient_id=patient.id)
        .order_by(Encounter.created_at.desc())
        .all()
    )
    note_count = 0
    for encounter in encounters:
        # Intake stores service form answers as notes on the encounter.
        notes = encounter.notes.order_by(Note.created_at.asc()).all()
        encounter.intake_notes_list = notes
        note_count += len(notes)

    # Patient-level notes not tied to a visit (rare, but include under intake summary).
    orphan_notes = (
        Note.query.filter(
            Note.patient_id == patient.id,
            Note.encounter_id.is_(None),
        )
        .order_by(Note.created_at.asc())
        .all()
    )
    note_count += len(orphan_notes)
    if note_count:
        log_phi_list(
            "notes",
            row_count=note_count,
            detail=f"service intake notes viewed on patient_id={patient.id}",
        )
    if encounters:
        log_phi_list(
            "encounters",
            row_count=len(encounters),
            detail=f"service requests viewed on patient_id={patient.id}",
        )

    return render_template(
        "client/patient_detail.html",
        patient=patient,
        encounters=encounters,
        orphan_notes=orphan_notes,
        service_labels=SERVICE_LABELS,
    )


@client_patient_bp.route("/api/patient-lookup")
def patient_lookup():
    """Strict patient existence check for service intake forms.

    Returns a patient only on unambiguous match (Patient ID, or unique exact
    first+last name). Never returns a "best guess" among multiple people.
    """
    from audit import log_phi_select

    query = (request.args.get("q") or "").strip()
    result = resolve_patient_lookup(query)
    patient = result["patient"]

    if result["status"] != LOOKUP_FOUND or patient is None:
        return jsonify(
            {
                "found": False,
                "status": result["status"],
                "message": result["message"],
            }
        )

    log_phi_select(
        "patients",
        record_id=patient.id,
        patient_id=patient.id,
        client_id=patient.client_id,
        detail="service intake patient lookup",
    )
    return jsonify(
        {
            "found": True,
            "status": LOOKUP_FOUND,
            "patient_id": patient.id,
            "display_name": patient.full_name,
            "message": result["message"],
        }
    )


@client_patient_bp.route("/outpatient-procedure-request", methods=["GET", "POST"])
def outpatient_procedure_request():
    """Public form attached to the OutPatient Procedure Advocacy service.

    Requires an existing patient record (patient_id). Links service metadata
    to that patient + a new outpatient-procedure encounter.
    """
    form = OutpatientProcedureForm()
    _prefill_service_intake_form(form)
    if form.validate_on_submit():
        intake_notes = format_outpatient_procedure_notes(
            procedure_name=form.procedure_name.data,
            first_time_with_provider=form.first_time_with_provider.data,
            procedure_visit_type=form.procedure_visit_type.data,
            provider_name=form.provider_name.data,
            provider_office_name=form.provider_office_name.data,
            provider_specialty=form.provider_specialty.data,
            provider_phone=form.provider_phone.data,
            provider_address=form.provider_address.data,
            hipaa_release_for_provider=form.hipaa_release_for_provider.data,
            notes=form.notes.data,
        )
        try:
            _client, patient, encounter = create_intake_request(
                patient_name=(form.patient_name.data or "").strip() or None,
                contact_name=form.contact_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip().lower(),
                service="outpatient-procedure",
                hospital_name=(form.provider_office_name.data or "").strip() or None,
                notes=intake_notes,
                patient_must_exist=True,
                patient_id=_parse_hidden_patient_id(form),
            )
            if patient and encounter:
                msg = (
                    "Thank you! Your outpatient procedure advocacy request has been "
                    "submitted. Our team will contact you soon."
                )
            else:
                msg = "Thank you! Your request has been submitted. Our team will contact you soon."
            flash(msg, "success")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "client/outpatient_procedure_request.html",
                form=form,
            )
        return redirect(url_for("client_patient.outpatient_procedure_request"))
    return render_template("client/outpatient_procedure_request.html", form=form)


@client_patient_bp.route("/er-visit-request", methods=["GET", "POST"])
def er_visit_request():
    """Public form attached to the ER Visit service.

    Requires an existing patient record (patient_id). Links ER intake answers
    to that patient + a new er-admittance encounter.
    """
    form = ErVisitForm()
    _prefill_service_intake_form(form)
    if form.validate_on_submit():
        intake_notes = format_er_visit_notes(
            chief_complaint=form.chief_complaint.data,
            first_hospital_encounter=form.first_hospital_encounter.data,
            hospital_name=form.hospital_name.data,
            hospital_address=form.hospital_address.data,
            hospital_city=form.hospital_city.data,
            hospital_state=form.hospital_state.data,
            nok_name=form.nok_name.data,
            nok_phone=form.nok_phone.data,
            nok_email=form.nok_email.data,
            additional_comments=form.additional_comments.data,
        )
        try:
            _client, patient, encounter = create_intake_request(
                patient_name=(form.patient_name.data or "").strip() or None,
                contact_name=form.contact_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip().lower(),
                service="er-admittance",
                hospital_name=(form.hospital_name.data or "").strip() or None,
                hospital_address=(form.hospital_address.data or "").strip() or None,
                hospital_city=(form.hospital_city.data or "").strip() or None,
                hospital_state=(form.hospital_state.data or "").strip() or None,
                notes=intake_notes,
                patient_must_exist=True,
                patient_id=_parse_hidden_patient_id(form),
            )
            if patient and encounter:
                msg = (
                    "Thank you! Your ER Visit advocacy request has been submitted. "
                    "Our team will contact you soon."
                )
            else:
                msg = "Thank you! Your request has been submitted. Our team will contact you soon."
            flash(msg, "success")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("client/er_visit_request.html", form=form)
        return redirect(url_for("client_patient.er_visit_request"))
    return render_template("client/er_visit_request.html", form=form)


@client_patient_bp.route("/service-request", methods=["GET", "POST"])
def service_request():
    from config import SERVICE_INTAKE_ENDPOINTS, SERVICE_LABELS

    form = PatientInfoForm()
    if form.validate_on_submit():
        # Services with dedicated intake forms: save patient first, then hand off.
        service = (form.service.data or "").strip()
        intake_endpoint = SERVICE_INTAKE_ENDPOINTS.get(service)
        if intake_endpoint:
            label = SERVICE_LABELS.get(service, "this service")
            patient_name = (form.patient_name.data or "").strip() or (
                form.contact_name.data or ""
            ).strip()
            try:
                _client, patient = ensure_client_and_patient(
                    contact_name=form.contact_name.data.strip(),
                    phone=form.phone.data.strip(),
                    email=form.email.data.strip().lower(),
                    patient_name=patient_name,
                )
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("client/service_request.html", form=form)

            flash(
                f"Patient record saved (ID {patient.id}). Complete the {label} "
                "form for visit-specific details.",
                "success",
            )
            return redirect(
                url_for(
                    intake_endpoint,
                    patient_id=patient.id,
                    patient_name=patient.full_name,
                    contact_name=form.contact_name.data.strip(),
                    phone=form.phone.data.strip(),
                    email=form.email.data.strip().lower(),
                )
            )
        try:
            _client, patient, encounter = create_intake_request(
                patient_name=(form.patient_name.data or "").strip() or None,
                contact_name=form.contact_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip().lower(),
                service=form.service.data,
                hospital_name=(form.hospital.data or "").strip() or None,
                notes=(form.notes.data or "").strip() or None,
            )
            if patient and encounter:
                msg = "Thank you! Your patient request has been submitted. Our team will contact you soon."
            elif patient:
                msg = "Thank you! Patient information has been saved. Our team will follow up with you soon."
            else:
                msg = "Thank you! Your contact information has been saved. You can add patient details later."
            flash(msg, "success")
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("client/service_request.html", form=form)
        return redirect(url_for("client_patient.service_request"))
    return render_template("client/service_request.html", form=form)
