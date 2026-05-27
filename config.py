import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "starthere.db")


def _database_uri() -> str:
    uri = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-production")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


CONTACTS = [
    {
        "name": "Georgette Johnson",
        "title": "Patient Advocate",
        "email": os.environ.get("CONTACT_GEORGETTE_EMAIL", ""),
        "phone": os.environ.get("CONTACT_GEORGETTE_PHONE", ""),
    },
    {
        "name": "Dawn Criswell",
        "title": "Patient Advocate",
        "email": os.environ.get("CONTACT_DAWN_EMAIL", ""),
        "phone": os.environ.get("CONTACT_DAWN_PHONE", ""),
    },
    {
        "name": "Larry Horton",
        "title": "Patient Advocate",
        "email": os.environ.get("CONTACT_LARRY_EMAIL", ""),
        "phone": os.environ.get("CONTACT_LARRY_PHONE", ""),
    },
]

SERVICE_CHOICES = [
    ("er-admittance", "ER Admittance – Patient Advocate"),
    ("in-hospital", "In-Hospital Patient Visits"),
    ("discharge", "Discharge Support – Patient Advocacy"),
    ("followup", "After Encounter 10/20/30 Days Followup"),
]

SERVICE_LABELS = dict(SERVICE_CHOICES)

ENCOUNTER_STATUS_CHOICES = [
    ("requested", "Requested"),
    ("scheduled", "Scheduled"),
    ("active", "Active"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

ACCOUNT_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("closed", "Closed"),
]

INVOICE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("sent", "Sent"),
    ("paid", "Paid"),
    ("overdue", "Overdue"),
    ("cancelled", "Cancelled"),
]
