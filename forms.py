from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    EmailField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from config import (
    ACCOUNT_STATUS_CHOICES,
    ENCOUNTER_STATUS_CHOICES,
    INVOICE_STATUS_CHOICES,
    SERVICE_CHOICES,
)


class PatientInfoForm(FlaskForm):
    """Public service request form (creates client, patient, and encounter)."""
    patient_name = StringField(
        "Patient Full Name",
        validators=[DataRequired(), Length(max=200)],
    )
    contact_name = StringField(
        "Primary Contact Name",
        validators=[DataRequired(), Length(max=200)],
    )
    phone = StringField(
        "Phone Number",
        validators=[DataRequired(), Length(max=50)],
    )
    email = EmailField(
        "Email Address",
        validators=[DataRequired(), Email(), Length(max=200)],
    )
    service = SelectField(
        "Service Requested",
        choices=[("", "Select a service...")] + SERVICE_CHOICES,
        validators=[DataRequired()],
    )
    hospital = StringField(
        "Hospital / Facility (if known)",
        validators=[Optional(), Length(max=200)],
    )
    notes = TextAreaField(
        "Additional Information",
        validators=[Optional(), Length(max=5000)],
    )


def nullable_int(value):
    if value in (None, "", "0", 0):
        return None
    return int(value)


class EncounterForm(FlaskForm):
    patient_id = SelectField("Patient", coerce=int, validators=[DataRequired()])
    advocate_id = SelectField(
        "Advocate", coerce=nullable_int, validators=[Optional()]
    )
    provider_id = SelectField(
        "Provider", coerce=nullable_int, validators=[Optional()]
    )
    hospital_id = SelectField(
        "Hospital", coerce=nullable_int, validators=[Optional()]
    )
    home_health_facility_id = SelectField(
        "Home Health Facility", coerce=nullable_int, validators=[Optional()]
    )
    encounter_type = SelectField(
        "Service Type",
        choices=SERVICE_CHOICES,
        validators=[DataRequired()],
    )
    status = SelectField(
        "Status",
        choices=ENCOUNTER_STATUS_CHOICES,
        validators=[DataRequired()],
    )
    scheduled_at = StringField("Scheduled Date/Time", validators=[Optional()])
    started_at = StringField("Started Date/Time", validators=[Optional()])
    ended_at = StringField("Ended Date/Time", validators=[Optional()])


class NoteForm(FlaskForm):
    content = TextAreaField(
        "Note",
        validators=[DataRequired(), Length(max=5000)],
    )
    author = StringField("Author", validators=[Optional(), Length(max=200)])


class EncounterSearchForm(FlaskForm):
    q = StringField("Search", validators=[Optional(), Length(max=200)])
    status = SelectField(
        "Status",
        choices=[("", "All statuses")] + ENCOUNTER_STATUS_CHOICES,
        validators=[Optional()],
    )
    encounter_type = SelectField(
        "Service Type",
        choices=[("", "All services")] + SERVICE_CHOICES,
        validators=[Optional()],
    )


class AccountSearchForm(FlaskForm):
    q = StringField("Search", validators=[Optional(), Length(max=200)])
    status = SelectField(
        "Status",
        choices=[("", "All statuses")] + ACCOUNT_STATUS_CHOICES,
        validators=[Optional()],
    )


class AccountForm(FlaskForm):
    list_id = SelectField("Account Type", coerce=int, validators=[DataRequired()])
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    patient_id = SelectField("Patient", coerce=nullable_int, validators=[Optional()])
    name = StringField("Account Name", validators=[DataRequired(), Length(max=200)])
    account_number = StringField(
        "Account Number", validators=[Optional(), Length(max=50)]
    )
    balance = DecimalField(
        "Balance",
        places=2,
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    status = SelectField(
        "Status",
        choices=ACCOUNT_STATUS_CHOICES,
        validators=[DataRequired()],
    )


class BillingForm(FlaskForm):
    note_id = SelectField("Related Note", coerce=int, validators=[DataRequired()])
    description = StringField("Description", validators=[Optional(), Length(max=300)])
    amount = DecimalField(
        "Amount",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )


class InvoiceForm(FlaskForm):
    invoice_number = StringField(
        "Invoice Number",
        validators=[DataRequired(), Length(max=50)],
    )
    issue_date = DateField("Issue Date", validators=[DataRequired()], default=date.today)
    due_date = DateField("Due Date", validators=[Optional()])
    status = SelectField(
        "Status",
        choices=INVOICE_STATUS_CHOICES,
        validators=[DataRequired()],
    )
    description = StringField(
        "Line Item Description",
        validators=[DataRequired(), Length(max=300)],
    )
    quantity = DecimalField(
        "Quantity",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
        default=1,
    )
    unit_price = DecimalField(
        "Unit Price",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )


def empty_select(label):
    return [(0, f"Select {label}...")]


class ClientInfoForm(FlaskForm):
    name = StringField("Client Name", validators=[DataRequired(), Length(max=200)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    email = EmailField("Email", validators=[Optional(), Email(), Length(max=200)])
    address = StringField("Address", validators=[Optional(), Length(max=300)])
    patient_id = SelectField(
        "Linked Patient",
        coerce=nullable_int,
        validators=[Optional()],
    )


class PatientRecordForm(FlaskForm):
    client_id = SelectField("Linked Client", coerce=int, validators=[DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    email = EmailField("Email", validators=[Optional(), Email(), Length(max=200)])


class HospitalForm(FlaskForm):
    name = StringField("Hospital Name", validators=[DataRequired(), Length(max=200)])
    address = StringField("Address", validators=[Optional(), Length(max=300)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])


class AdvocateEntityForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    title = StringField("Title", validators=[Optional(), Length(max=100)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    email = EmailField("Email", validators=[Optional(), Email(), Length(max=200)])
    active = SelectField(
        "Status",
        choices=[("1", "Active"), ("0", "Inactive")],
        validators=[DataRequired()],
    )


class HomeHealthFacilityForm(FlaskForm):
    name = StringField("Facility Name", validators=[DataRequired(), Length(max=200)])
    address = StringField("Address", validators=[Optional(), Length(max=300)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])


class TimeCardForm(FlaskForm):
    advocate_id = SelectField("Advocate", coerce=int, validators=[DataRequired()])
    encounter_id = SelectField("Encounter", coerce=nullable_int, validators=[Optional()])
    work_date = DateField("Work Date", validators=[DataRequired()], default=date.today)
    hours = DecimalField(
        "Hours",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01, max=24)],
    )
    description = StringField("Description", validators=[Optional(), Length(max=300)])


class AdHocQueryForm(FlaskForm):
    sql = TextAreaField(
        "SQL Query (SELECT only)",
        validators=[DataRequired(), Length(max=5000)],
        render_kw={"rows": 8, "placeholder": "SELECT id, name FROM clients LIMIT 25;"},
    )
