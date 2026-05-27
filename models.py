from datetime import datetime, timezone

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


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    address = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="clients")
    patients = db.relationship("Patient", back_populates="client", lazy="dynamic")
    accounts = db.relationship("Account", back_populates="client", lazy="dynamic")


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="patients")
    client = db.relationship("Client", back_populates="patients")
    relationships = db.relationship(
        "PatientRelationship", back_populates="patient", lazy="dynamic"
    )
    encounters = db.relationship("Encounter", back_populates="patient", lazy="dynamic")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


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


class Advocate(db.Model):
    __tablename__ = "advocates"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    company = db.relationship("Company", back_populates="advocates")
    encounters = db.relationship("Encounter", back_populates="advocate", lazy="dynamic")


class Provider(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    specialty = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    npi = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounters = db.relationship("Encounter", back_populates="provider", lazy="dynamic")


class Hospital(db.Model):
    __tablename__ = "hospitals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300))
    phone = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounters = db.relationship("Encounter", back_populates="hospital", lazy="dynamic")


class HomeHealthFacility(db.Model):
    __tablename__ = "home_health_facilities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300))
    phone = db.Column(db.String(50))
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
    encounter_id = db.Column(db.Integer, db.ForeignKey("encounters.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    encounter = db.relationship("Encounter", back_populates="notes")
    billings = db.relationship("Billing", back_populates="note", lazy="dynamic")


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
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"))
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"))
    name = db.Column(db.String(200), nullable=False)
    account_number = db.Column(db.String(50))
    balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(50), nullable=False, default="active")
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

    invoice = db.relationship("Invoice", back_populates="items")
