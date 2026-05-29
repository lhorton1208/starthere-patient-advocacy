from auth import employee_required
from forms import ClientInfoForm, PatientInfoForm, PatientRecordForm, empty_select
from intake import create_intake_request
from models import Client, Company, Patient, db
from flask import Blueprint, flash, redirect, render_template, request, url_for
from seed import COMPANY_NAME

client_patient_bp = Blueprint("client_patient", __name__, url_prefix="/client")


def _company():
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        raise RuntimeError("StartHere company record is missing.")
    return company


def _populate_client_form(form, client=None):
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    form.patient_id.choices = [(0, "None")] + [
        (p.id, p.full_name) for p in patients
    ]
    if client and client.patients.count():
        form.patient_id.data = client.patients.first().id


def _populate_patient_form(form, patient=None):
    clients = Client.query.order_by(Client.name).all()
    form.client_id.choices = empty_select("client") + [
        (c.id, c.name) for c in clients
    ]
    if patient:
        form.client_id.data = patient.client_id


@client_patient_bp.route("/client-info")
@employee_required
def list_clients():
    rows = Client.query.order_by(Client.name).all()
    return render_template("client/client_list.html", rows=rows)


@client_patient_bp.route("/client-info/new", methods=["GET", "POST"])
@client_patient_bp.route("/client-info/<int:client_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_client(client_id=None):
    company = _company()
    client = Client.query.get(client_id) if client_id else None
    form = ClientInfoForm(obj=client)
    _populate_client_form(form, client)

    if form.validate_on_submit():
        record = client or Client(company_id=company.id)
        record.name = form.name.data.strip()
        record.phone = (form.phone.data or "").strip() or None
        record.email = (form.email.data or "").strip().lower() or None
        record.address = (form.address.data or "").strip() or None
        if not client:
            db.session.add(record)
            db.session.flush()

        if form.patient_id.data:
            patient = Patient.query.get(form.patient_id.data)
            if patient:
                patient.client_id = record.id

        db.session.commit()
        flash("Client saved.", "success")
        return redirect(url_for("client_patient.view_client", client_id=record.id))

    return render_template(
        "client/client_form.html",
        form=form,
        client=client,
        title="Edit Client" if client else "New Client",
    )


@client_patient_bp.route("/client-info/<int:client_id>")
@employee_required
def view_client(client_id):
    client = Client.query.get_or_404(client_id)
    patients = client.patients.order_by(Patient.last_name).all()
    return render_template("client/client_detail.html", client=client, patients=patients)


@client_patient_bp.route("/patient-info")
@employee_required
def list_patients():
    rows = Patient.query.join(Client).order_by(Patient.last_name, Patient.first_name).all()
    return render_template("client/patient_list.html", rows=rows)


@client_patient_bp.route("/patient-info/new", methods=["GET", "POST"])
@client_patient_bp.route("/patient-info/<int:patient_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_patient(patient_id=None):
    company = _company()
    patient = Patient.query.get(patient_id) if patient_id else None
    form = PatientRecordForm(obj=patient)
    _populate_patient_form(form, patient)
    from flask import request
    preselect_client = request.args.get("client_id", type=int)
    if preselect_client and not patient:
        form.client_id.data = preselect_client

    if form.validate_on_submit():
        record = patient or Patient(company_id=company.id)
        record.client_id = form.client_id.data
        record.first_name = form.first_name.data.strip()
        record.last_name = form.last_name.data.strip()
        record.date_of_birth = form.date_of_birth.data
        record.phone = (form.phone.data or "").strip() or None
        record.email = (form.email.data or "").strip().lower() or None
        if not patient:
            db.session.add(record)
        db.session.commit()
        flash("Patient saved.", "success")
        return redirect(url_for("client_patient.view_patient", patient_id=record.id))

    return render_template(
        "client/patient_form.html",
        form=form,
        patient=patient,
        title="Edit Patient" if patient else "New Patient",
    )


@client_patient_bp.route("/patient-info/<int:patient_id>")
@employee_required
def view_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return render_template("client/patient_detail.html", patient=patient)


@client_patient_bp.route("/service-request", methods=["GET", "POST"])
def service_request():
    form = PatientInfoForm()
    if form.validate_on_submit():
        create_intake_request(
            patient_name=form.patient_name.data.strip(),
            contact_name=form.contact_name.data.strip(),
            phone=form.phone.data.strip(),
            email=form.email.data.strip().lower(),
            service=form.service.data,
            hospital_name=(form.hospital.data or "").strip() or None,
            notes=(form.notes.data or "").strip() or None,
        )
        flash(
            "Thank you! Your request has been submitted. A member of our team will contact you soon.",
            "success",
        )
        return redirect(url_for("client_patient.service_request"))
    return render_template("client/service_request.html", form=form)
