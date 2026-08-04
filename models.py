from datetime import date, datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def _utcnow():
    return datetime.now(timezone.utc)


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    address = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    clients = db.relationship("Client", back_populates="company", lazy="dynamic")
    patients = db.relationship("Patient", back_populates="company", lazy="dynamic")
    advocates = db.relationship("Advocate", back_populates="company", lazy="dynamic")


class RelationshipToPatient(db.Model):
    __tablename__ = "relationship_to_patient"

    id = db.Column(db.Integer, primary_key=True)
    relationship = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_legal_guardian = db.Column(db.Boolean, nullable=False, default=False)
    is_power_of_attorney = db.Column(db.Boolean, nullable=False, default=False)

    clients = db.relationship("Client", back_populates="relationship_type", lazy="dynamic")


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    # Legacy single-field name (kept for backward compatibility in lists/reports).
    name = db.Column(db.String(200), nullable=False, default="")
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    middle_name = db.Column(db.String(255))
    suffix = db.Column(db.String(10))
    prefix = db.Column(db.String(255))
    account_number = db.Column(db.String(255))
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    phone_number2 = db.Column(db.String(32))
    email = db.Column(db.String(255), unique=True)
    relationship_to_patient_id = db.Column(
        db.Integer, db.ForeignKey("relationship_to_patient.id")
    )
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="clients")
    relationship_type = db.relationship(
        "RelationshipToPatient", back_populates="clients"
    )
    linked_patient = db.relationship(
        "Patient",
        foreign_keys=[patient_id],
        back_populates="linked_client",
        uselist=False,
    )
    patients = db.relationship(
        "Patient",
        foreign_keys="Patient.client_id",
        back_populates="client",
        lazy="dynamic",
    )
    accounts = db.relationship("Account", back_populates="client", lazy="dynamic")

    @property
    def display_name(self):
        if self.first_name or self.last_name:
            parts = [self.prefix, self.first_name, self.middle_name, self.last_name, self.suffix]
            return " ".join(p for p in parts if p)
        return self.name or ""

    def sync_name_fields(self):
        if self.first_name or self.last_name:
            self.name = self.display_name
        elif self.name and not self.first_name:
            parts = self.name.strip().split()
            if parts:
                self.first_name = parts[0]
                self.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(255))
    last_name = db.Column(db.String(100), nullable=False)
    prefix = db.Column(db.String(32))
    suffix = db.Column(db.String(32))
    date_of_birth = db.Column(db.Date)
    last4_ssn = db.Column(db.String(4))
    last_encounter_date = db.Column(db.Date)
    created_by = db.Column(db.String(255))
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    phone_mobile = db.Column(db.String(32))
    phone_landline = db.Column(db.String(32))
    email = db.Column(db.String(255), unique=True)
    mood = db.Column(db.String(255))
    mental_state = db.Column(db.String(255))
    patient_medications_id = db.Column(
        db.Integer, db.ForeignKey("patient_medications.id")
    )
    primary_provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"))
    intake_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="patients")
    client = db.relationship(
        "Client",
        foreign_keys=[client_id],
        back_populates="patients",
    )
    linked_client = db.relationship(
        "Client",
        foreign_keys="Client.patient_id",
        back_populates="linked_patient",
        uselist=False,
    )
    primary_provider = db.relationship(
        "Provider",
        foreign_keys=[primary_provider_id],
        back_populates="primary_patients",
    )
    relationships = db.relationship(
        "PatientRelationship", back_populates="patient", lazy="dynamic"
    )
    encounters = db.relationship("Encounter", back_populates="patient", lazy="dynamic")
    medications = db.relationship(
        "PatientMedication",
        foreign_keys="PatientMedication.patient_id",
        back_populates="patient",
        lazy="dynamic",
    )
    medication_profile = db.relationship(
        "PatientMedication",
        foreign_keys=[patient_medications_id],
        uselist=False,
    )

    @property
    def full_name(self):
        parts = [self.prefix, self.first_name, self.middle_name, self.last_name, self.suffix]
        return " ".join(p for p in parts if p).strip()

    @property
    def dob(self):
        return self.date_of_birth


class PatientRelationship(db.Model):
    __tablename__ = "patient_relationships"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    related_name = db.Column(db.String(200), nullable=False)
    relationship_type = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    patient = db.relationship("Patient", back_populates="relationships")


class PatientMedication(db.Model):
    __tablename__ = "patient_medications"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    medication_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    dosage = db.Column(db.String(255))
    frequency = db.Column(db.String(255))
    prescribed_by = db.Column(db.String(255))
    is_compliant = db.Column(db.Boolean)
    pharmacy = db.Column(db.String(255))
    pharmacy_phone_number = db.Column(db.String(32))
    address = db.Column(db.String(255))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    patient = db.relationship(
        "Patient",
        foreign_keys=[patient_id],
        back_populates="medications",
    )


class Advocate(db.Model):
    __tablename__ = "advocates"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(255))
    middle_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    title = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    phone_mobile = db.Column(db.String(32))
    phone_landline = db.Column(db.String(32))
    email = db.Column(db.String(200))
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    active = db.Column(db.Boolean, nullable=False, default=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="advocates")
    encounters = db.relationship("Encounter", back_populates="advocate", lazy="dynamic")
    time_cards = db.relationship("TimeCard", back_populates="advocate", lazy="dynamic")
    notes = db.relationship("Note", back_populates="advocate", lazy="dynamic")

    def sync_name_fields(self):
        if self.first_name or self.last_name:
            self.name = " ".join(
                p for p in [self.first_name, self.last_name] if p
            ).strip()

    @property
    def has_login(self) -> bool:
        return bool(self.username and self.password_hash)

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def clear_login(self) -> None:
        self.username = None
        self.password_hash = None
        self.is_admin = False


class Provider(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default="")
    prefix = db.Column(db.String(32))
    first_name = db.Column(db.String(255))
    middle_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    title = db.Column(db.String(100))
    location_id = db.Column(db.Integer)
    specialty = db.Column(db.String(150))
    affiliation = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    npi = db.Column(db.String(20))
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounters = db.relationship("Encounter", back_populates="provider", lazy="dynamic")
    primary_patients = db.relationship(
        "Patient",
        foreign_keys="Patient.primary_provider_id",
        back_populates="primary_provider",
        lazy="dynamic",
    )

    @property
    def display_name(self):
        if self.first_name or self.last_name:
            return " ".join(
                p
                for p in [self.prefix, self.first_name, self.middle_name, self.last_name]
                if p
            ).strip()
        return self.name or ""

    def sync_name_fields(self):
        if self.first_name or self.last_name:
            self.name = self.display_name
        elif self.name and not self.first_name:
            parts = self.name.strip().split()
            if parts:
                self.first_name = parts[0]
                self.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    @property
    def choice_label(self):
        label = self.display_name or f"Provider #{self.id}"
        if self.specialty:
            label = f"{label} — {self.specialty}"
        elif self.affiliation:
            label = f"{label} — {self.affiliation}"
        return label


class Hospital(db.Model):
    __tablename__ = "hospitals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    main_phone_number = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounters = db.relationship("Encounter", back_populates="hospital", lazy="dynamic")


class HomeHealthFacility(db.Model):
    __tablename__ = "home_health_facilities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    facility_phone_number = db.Column(db.String(32))
    point_of_contact_name = db.Column(db.String(255))
    point_of_contact_phone_number = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounters = db.relationship(
        "Encounter", back_populates="home_health_facility", lazy="dynamic"
    )


class Encounter(db.Model):
    __tablename__ = "encounters"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    advocate_id = db.Column(db.Integer, db.ForeignKey("advocates.id"))
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"))
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"))
    home_health_facility_id = db.Column(
        db.Integer, db.ForeignKey("home_health_facilities.id")
    )
    encounter_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="requested")
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    patient = db.relationship("Patient", back_populates="encounters")
    advocate = db.relationship("Advocate", back_populates="encounters")
    provider = db.relationship("Provider", back_populates="encounters")
    hospital = db.relationship("Hospital", back_populates="encounters")
    home_health_facility = db.relationship(
        "HomeHealthFacility", back_populates="encounters"
    )
    notes = db.relationship("Note", back_populates="encounter", lazy="dynamic")


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    encounter_id = db.Column(db.Integer, db.ForeignKey("encounters.id"))
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"))
    advocate_id = db.Column(db.Integer, db.ForeignKey("advocates.id"))
    content = db.Column(db.Text, nullable=False, default="")
    description = db.Column(db.Text)
    note_text = db.Column(db.Text)
    internal_only = db.Column(db.Boolean, nullable=False, default=False)
    author = db.Column(db.String(200))
    note_datetime = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounter = db.relationship("Encounter", back_populates="notes")
    patient = db.relationship("Patient", backref=db.backref("notes", lazy="dynamic"))
    advocate = db.relationship("Advocate", back_populates="notes")
    billings = db.relationship("Billing", back_populates="note", lazy="dynamic")

    @property
    def body(self):
        return self.note_text or self.content


class LookupList(db.Model):
    __tablename__ = "lookup_lists"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    list_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    accounts = db.relationship("Account", back_populates="lookup_list", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("name", "list_type", name="uq_lookup_list_name_type"),
    )


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("lookup_lists.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"))
    name = db.Column(db.String(200), nullable=False)
    account_number = db.Column(db.String(50))
    balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(50), nullable=False, default="active")
    billing_address = db.Column(db.String(255))
    city = db.Column(db.String(255))
    state = db.Column(db.String(255))
    zip_code = db.Column(db.String(255))
    payment_method = db.Column(db.String(255))
    credit_card_last4 = db.Column(db.String(4))
    exp_date = db.Column(db.String(16))
    last_payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    lookup_list = db.relationship("LookupList", back_populates="accounts")
    client = db.relationship("Client", back_populates="accounts")
    patient = db.relationship("Patient")
    billings = db.relationship("Billing", back_populates="account", lazy="dynamic")
    invoices = db.relationship("Invoice", back_populates="account", lazy="dynamic")


class Billing(db.Model):
    __tablename__ = "billings"

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey("notes.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    description = db.Column(db.String(300))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    billed_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    note = db.relationship("Note", back_populates="billings")
    account = db.relationship("Account", back_populates="billings")


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    invoice_sub_total = db.Column(db.Numeric(10, 2))
    tax = db.Column(db.Numeric(10, 2))
    invoice_total = db.Column(db.Numeric(10, 2))
    description = db.Column(db.String(255))
    status = db.Column(db.String(50), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    account = db.relationship("Account", back_populates="invoices")
    items = db.relationship("InvoiceItem", back_populates="invoice", lazy="dynamic")


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    line_item_total = db.Column(db.Numeric(10, 2))

    invoice = db.relationship("Invoice", back_populates="items")


class TimeCard(db.Model):
    __tablename__ = "time_cards"

    id = db.Column(db.Integer, primary_key=True)
    advocate_id = db.Column(db.Integer, db.ForeignKey("advocates.id"), nullable=False)
    encounter_id = db.Column(db.Integer, db.ForeignKey("encounters.id"))
    work_date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    advocate = db.relationship("Advocate", back_populates="time_cards")
    encounter = db.relationship(
        "Encounter", backref=db.backref("time_cards", lazy="dynamic")
    )


class PhiAccessLog(db.Model):
    """Immutable audit trail of PHI access and mutation (no PHI values stored)."""

    __tablename__ = "phi_access_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)
    advocate_id = db.Column(db.Integer, db.ForeignKey("advocates.id"), index=True)
    actor_username = db.Column(db.String(64))
    actor_name = db.Column(db.String(200))
    action = db.Column(db.String(20), nullable=False, index=True)  # SELECT/INSERT/UPDATE/DELETE
    table_name = db.Column(db.String(100), nullable=False, index=True)
    record_id = db.Column(db.Integer, index=True)
    patient_id = db.Column(db.Integer, index=True)
    client_id = db.Column(db.Integer, index=True)
    detail = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))
    ip_address = db.Column(db.String(64))

    advocate = db.relationship(
        "Advocate", backref=db.backref("phi_access_logs", lazy="dynamic")
    )


def link_client_patient(client: Client, patient: Patient) -> None:
    """Keep bidirectional 0..1 links in sync."""
    patient.client_id = client.id
    client.patient_id = patient.id


def delete_patient_record(patient: Patient) -> None:
    """Remove a patient and dependent encounters, notes, and links."""
    from audit import ACTION_DELETE, log_phi_access

    patient_id = patient.id
    encounter_ids = [
        row[0]
        for row in db.session.query(Encounter.id)
        .filter_by(patient_id=patient.id)
        .all()
    ]

    note_filters = [Note.patient_id == patient.id]
    if encounter_ids:
        note_filters.append(Note.encounter_id.in_(encounter_ids))
    note_ids = [
        row[0]
        for row in db.session.query(Note.id).filter(db.or_(*note_filters)).all()
    ]

    # Bulk Query.delete paths skip ORM unit-of-work events; log identifiers only.
    if note_ids:
        log_phi_access(
            ACTION_DELETE,
            "billings",
            patient_id=patient_id,
            detail=f"cascade via notes [{','.join(str(i) for i in note_ids)}]",
        )
        Billing.query.filter(Billing.note_id.in_(note_ids)).delete(
            synchronize_session=False
        )
        log_phi_access(
            ACTION_DELETE,
            "notes",
            patient_id=patient_id,
            detail=f"cascade record_ids [{','.join(str(i) for i in note_ids)}]",
        )
        Note.query.filter(Note.id.in_(note_ids)).delete(synchronize_session=False)

    if encounter_ids:
        log_phi_access(
            ACTION_DELETE,
            "time_cards",
            patient_id=patient_id,
            detail=f"cascade via encounters [{','.join(str(i) for i in encounter_ids)}]",
        )
        TimeCard.query.filter(TimeCard.encounter_id.in_(encounter_ids)).delete(
            synchronize_session=False
        )
        log_phi_access(
            ACTION_DELETE,
            "encounters",
            patient_id=patient_id,
            detail=f"cascade record_ids [{','.join(str(i) for i in encounter_ids)}]",
        )
    Encounter.query.filter_by(patient_id=patient.id).delete(synchronize_session=False)

    rel_ids = [
        row[0]
        for row in db.session.query(PatientRelationship.id)
        .filter_by(patient_id=patient.id)
        .all()
    ]
    if rel_ids:
        log_phi_access(
            ACTION_DELETE,
            "patient_relationships",
            patient_id=patient_id,
            detail=f"cascade record_ids [{','.join(str(i) for i in rel_ids)}]",
        )
    PatientRelationship.query.filter_by(patient_id=patient.id).delete(
        synchronize_session=False
    )

    patient.patient_medications_id = None
    db.session.flush()
    med_ids = [
        row[0]
        for row in db.session.query(PatientMedication.id)
        .filter_by(patient_id=patient.id)
        .all()
    ]
    if med_ids:
        log_phi_access(
            ACTION_DELETE,
            "patient_medications",
            patient_id=patient_id,
            detail=f"cascade record_ids [{','.join(str(i) for i in med_ids)}]",
        )
    PatientMedication.query.filter_by(patient_id=patient.id).delete(
        synchronize_session=False
    )

    Account.query.filter_by(patient_id=patient.id).update(
        {Account.patient_id: None}, synchronize_session=False
    )
    Client.query.filter_by(patient_id=patient.id).update(
        {Client.patient_id: None}, synchronize_session=False
    )
    # ORM delete of the patient row is audited via the after_flush listener.
    db.session.delete(patient)
