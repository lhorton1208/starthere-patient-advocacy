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
        "patient relationship as a collaboration, meeting people where they were, "
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

DAWN_BIO = [
    (
        "Dawn Criswell is a nationally credentialed healthcare IT and patient "
        "advocacy professional with over two decades of experience bridging clinical "
        "operations, technology, and compassionate care. Holding a Master's in "
        "Healthcare Administration from Saint Joseph's University and a Bachelor's "
        "in Health Information Management from Temple University, Dawn combines deep "
        "technical expertise with a patient-first philosophy that defines StartHere's "
        "mission."
    ),
    (
        "As a Registered Health Information Administrator (RHIA) and Agile Certified "
        "Product Owner, Dawn has led enterprise initiatives across EHR systems, "
        "population health platforms, and AI-enabled workflows. Her background includes "
        "senior roles with organizations such as Siemens Health, IQVIA, and Allscripts "
        "(Veradigm), where she specialized in workflow mapping, interoperability "
        "(HL7/FHIR), and regulatory compliance."
    ),
    (
        "At StartHere Patient Advocacy, Dawn brings this unique blend of clinical "
        "insight and systems precision to empower patients and families navigating "
        "complex healthcare journeys. Her approach emphasizes transparency, education, "
        "and advocacy — ensuring every client receives informed, coordinated, and "
        "compassionate support from intake through resolution."
    ),
]

LARRY_BIO = [
    (
        "Larry Horton is a Founder and Principal of StartHere Patient Advocacy, "
        "where he helps individuals and families navigate the healthcare system with "
        "clarity, confidence, and compassionate support. A Marine Corps veteran with a "
        "background in Healthcare IT and Clinical Trials IT, Larry brings both "
        "professional expertise and personal commitment to patient advocacy. Inspired "
        "by his own family's experience with gaps in care coordination, he is dedicated "
        "to helping others make informed decisions and avoid preventable setbacks."
    ),
    (
        "Larry holds a Bachelor and Master degree in Computer Science from NC Central "
        "University and NC State University and an MBA from Kenan-Flagler Business "
        "School UNC Chapel Hill."
    ),
]

INFO_EMAIL = os.environ.get(
    "CONTACT_INFO_EMAIL", "info@startherepatientadvocacy.com"
)

CONTACTS = [
    {
        "name": "Dawn Criswell",
        "slug": "dawn-criswell",
        "credentials": "MS, RHIA, FAHIMA",
        "title": "Founder & Principal, StartHere Patient Advocacy LLC",
        "email": os.environ.get(
            "CONTACT_DAWN_EMAIL", "Dawn.Criswell@startherepatientadvocacy.com"
        ),
        "phone": os.environ.get("CONTACT_DAWN_PHONE", ""),
        "image": "dawn-criswell.png",
        "bio": DAWN_BIO,
    },
    {
        "name": "Georgette Darnell",
        "slug": "georgette-darnell",
        "legacy_name": "Georgette Johnson",
        "credentials": "RN, MHA",
        "title": "Founder & Principal, StartHere Patient Advocacy LLC",
        "email": os.environ.get(
            "CONTACT_GEORGETTE_EMAIL",
            "Georgette.Darnell@startherepatientadvocacy.com",
        ),
        "phone": os.environ.get("CONTACT_GEORGETTE_PHONE", ""),
        "image": "georgette-darnell.png",
        "bio": GEORGETTE_BIO,
    },
    {
        "name": "Larry Horton",
        "slug": "larry-horton",
        "title": "Founder & Principal, StartHere Patient Advocacy LLC",
        "email": os.environ.get(
            "CONTACT_LARRY_EMAIL", "Larry.Horton@startherepatientadvocacy.com"
        ),
        "phone": os.environ.get("CONTACT_LARRY_PHONE", ""),
        "image": "larry-horton.png",
        "bio": LARRY_BIO,
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
