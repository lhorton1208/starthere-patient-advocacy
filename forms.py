from flask_wtf import FlaskForm
from wtforms import EmailField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

from config import SERVICE_CHOICES


class PatientInfoForm(FlaskForm):
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
