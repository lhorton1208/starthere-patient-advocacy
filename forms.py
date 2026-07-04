from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional

from config import (
    ACCOUNT_STATUS_CHOICES,
    ENCOUNTER_STATUS_CHOICES,
    INVOICE_STATUS_CHOICES,
    SERVICE_CHOICES,
)


class OutpatientProcedureForm(FlaskForm):
    """Intake form for outpatient procedure advocacy requests."""
    patient_name = StringField(
        "Patient Name and/or Patient ID",
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
    procedure = StringField(
        "What is the procedure?",
        validators=[DataRequired(), Length(max=300)],
    )
    procedure_location = StringField(
        "Where is the procedure?",
        validators=[DataRequired(), Length(max=300)],
    )
    procedure_duration = StringField(
        "Duration of the procedure",
        validators=[Optional(), Length(max=100)],
    )
    provider_name = StringField(
        "Healthcare Provider Name",
        validators=[Optional(), Length(max=200)],
    )
    provider_phone = StringField(
        "Healthcare Provider Phone Number",
        validators=[Optional(), Length(max=50)],
    )
    procedure_preparation = TextAreaField(
        "Procedure Preparation",
        validators=[Optional(), Length(max=5000)],
        render_kw={"rows": 4},
    )
    procedure_medications = TextAreaField(
        "Procedure Medications",
        validators=[Optional(), Length(max=5000)],
        render_kw={"rows": 4},
    )
    notes = TextAreaField(
        "Notes",
        validators=[Optional(), Length(max=5000)],
        render_kw={"rows": 4},
    )


class PatientInfoForm(FlaskForm):
    """Public service request form (creates client, patient, and encounter)."""
    patient_name = StringField(
        "Patient Full Name (leave blank if same as contact or adding later)",
        validators=[Optional(), Length(max=200)],
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
        "Service Requested (required when adding a patient)",
        choices=[("", "Select a service...")] + SERVICE_CHOICES,
        validators=[Optional()],
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


class VisitNoteForm(FlaskForm):
    visit_number = SelectField(
        "Visit Number",
        coerce=nullable_int,
        validators=[Optional()],
    )
    patient_id = SelectField(
        "Patient ID / Name",
        coerce=int,
        validators=[DataRequired()],
    )
    advocate_id = SelectField(
        "Advocate Name",
        coerce=nullable_int,
        validators=[Optional()],
    )
    internal_only = BooleanField("Internal Only", default=False)
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    note_text = TextAreaField(
        "Note",
        validators=[DataRequired()],
        render_kw={"rows": 14, "placeholder": "Enter note text..."},
    )


class NotesReportForm(FlaskForm):
    filter_by = SelectField(
        "Filter By",
        choices=[
            ("all", "All notes"),
            ("visit", "Visit ID"),
            ("patient", "Patient ID"),
            ("advocate", "Advocate"),
        ],
        default="all",
    )
    entity_id = SelectField(
        "Selection",
        coerce=nullable_int,
        validators=[Optional()],
        default=0,
    )
    internal_only = SelectField(
        "Internal Only Notes",
        choices=[
            ("all", "Include all notes"),
            ("exclude", "Exclude internal only"),
            ("only", "Internal only"),
        ],
        default="all",
    )
    sort = SelectField(
        "Order by Timestamp",
        choices=[
            ("desc", "Newest first"),
            ("asc", "Oldest first"),
        ],
        default="desc",
    )


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
    prefix = StringField("Prefix", validators=[Optional(), Length(max=255)])
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=255)])
    middle_name = StringField("Middle Name", validators=[Optional(), Length(max=255)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=255)])
    suffix = StringField("Suffix", validators=[Optional(), Length(max=10)])
    account_number = StringField("Account Number", validators=[Optional(), Length(max=255)])
    phone = StringField("Primary Phone", validators=[Optional(), Length(max=50)])
    phone_number2 = StringField("Secondary Phone", validators=[Optional(), Length(max=32)])
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    relationship_to_patient_id = SelectField(
        "Relationship to Patient",
        coerce=nullable_int,
        validators=[Optional()],
    )
    address = StringField("Street Address", validators=[Optional(), Length(max=300)])
    city = StringField("City", validators=[Optional(), Length(max=255)])
    state = StringField("State", validators=[Optional(), Length(max=255)])
    zip_code = StringField("ZIP Code", validators=[Optional(), Length(max=255)])
    patient_id = SelectField(
        "Linked Patient",
        coerce=nullable_int,
        validators=[Optional()],
    )


class DeletePatientForm(FlaskForm):
    """CSRF-only form for patient delete POST."""


class PatientRecordForm(FlaskForm):
    client_id = SelectField("Linked Client", coerce=int, validators=[DataRequired()])
    prefix = StringField("Prefix", validators=[Optional(), Length(max=32)])
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=100)])
    middle_name = StringField("Middle Name", validators=[Optional(), Length(max=255)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=100)])
    suffix = StringField("Suffix", validators=[Optional(), Length(max=32)])
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    last4_ssn = StringField(
        "Last 4 of SSN",
        validators=[Optional(), Length(max=4)],
    )
    phone_mobile = StringField("Mobile Phone", validators=[Optional(), Length(max=32)])
    phone_landline = StringField(
        "Landline Phone", validators=[Optional(), Length(max=32)]
    )
    email = EmailField("Email", validators=[Optional(), Email(), Length(max=255)])
    address = StringField("Street Address", validators=[Optional(), Length(max=300)])
    city = StringField("City", validators=[Optional(), Length(max=255)])
    state = StringField("State", validators=[Optional(), Length(max=255)])
    zip_code = StringField("ZIP Code", validators=[Optional(), Length(max=255)])
    mood = StringField("Mood", validators=[Optional(), Length(max=255)])
    mental_state = StringField("Mental State", validators=[Optional(), Length(max=255)])
    intake_notes = TextAreaField(
        "Interview Notes",
        validators=[Optional(), Length(max=10000)],
        render_kw={
            "rows": 6,
            "placeholder": "Notes from the patient interview (advocate use).",
        },
    )


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


class RelationshipToPatientForm(FlaskForm):
    relationship = StringField(
        "Relationship",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"placeholder": "e.g. Son, Daughter, Spouse, Self"},
    )
    description = StringField(
        "Description",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"placeholder": "e.g. Son of patient"},
    )
    is_legal_guardian = SelectField(
        "Legal Guardian",
        choices=[("0", "No"), ("1", "Yes")],
        validators=[DataRequired()],
        default="0",
    )
    is_power_of_attorney = SelectField(
        "Power of Attorney",
        choices=[("0", "No"), ("1", "Yes")],
        validators=[DataRequired()],
        default="0",
    )


class TimeCardForm(FlaskForm):
    advocate_id = SelectField(
        "Advocate",
        coerce=int,
        validators=[DataRequired(), NumberRange(min=1)],
    )
    encounter_id = SelectField(
        "Visit ID",
        coerce=int,
        validators=[DataRequired(), NumberRange(min=1)],
    )
    work_date = DateField("Work Date", validators=[DataRequired()], default=date.today)
    hours = DecimalField(
        "Hours",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01, max=24)],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=300)],
        render_kw={"rows": 4, "placeholder": "Brief summary of work performed during the visit..."},
    )


class AdHocQueryForm(FlaskForm):
    sql = TextAreaField(
        "SQL Query (SELECT only)",
        validators=[DataRequired(), Length(max=5000)],
        render_kw={"rows": 8, "placeholder": "SELECT id, name FROM clients LIMIT 25;"},
    )


class LoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(max=64)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(max=128)],
    )


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )


class AdvocateLoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=64)],
        render_kw={"autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[Optional(), Length(min=8, max=128)],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[Optional(), Length(min=8, max=128)],
    )
    is_admin = BooleanField("Administrator (can manage advocate logins)")
