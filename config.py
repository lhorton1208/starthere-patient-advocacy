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


GEORGETTE_BIO = [
    (
        "With more than 20 years of nursing experience across inpatient, outpatient, "
        "home health, nursing home, and case management settings, I have built my "
        "career around one unwavering belief: that patients and their families deserve "
        "to be at the center of every healthcare decision."
    ),
    (
        "Throughout my clinical career as a Registered Nurse, I approached each "
        "patient relationship as a collaboration — meeting people where they were, "
        "leading with empathy, and ensuring that compassion was never a secondary "
        "consideration. That commitment to patient-centered care is what drew me to "
        "nursing, and it is what drives the work I do today."
    ),
    (
        "Healthcare has changed dramatically. Artificial intelligence now schedules "
        "appointments. Patient portals have replaced phone calls. For many patients, "
        "particularly older adults and those managing complex conditions, this shifting "
        "landscape is disorienting and isolating. At StartHere, I serve as your guide, "
        "your voice, and your advocate, so that you are never left behind."
    ),
]

CONTACTS = [
    {
        "name": "Georgette Darnell",
        "legacy_name": "Georgette Johnson",
        "title": "Patient Advocate",
        "email": os.environ.get("CONTACT_GEORGETTE_EMAIL", ""),
        "phone": os.environ.get("CONTACT_GEORGETTE_PHONE", ""),
        "image": "georgette-darnell.png",
        "bio": GEORGETTE_BIO,
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
