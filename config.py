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
    # FHIR / SMART Backend Services (client_credentials + client secret)
    FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "").strip()
    FHIR_TOKEN_URL = os.environ.get("FHIR_TOKEN_URL", "").strip()
    FHIR_CLIENT_ID = os.environ.get("FHIR_CLIENT_ID", "").strip()
    FHIR_CLIENT_SECRET = os.environ.get("FHIR_CLIENT_SECRET", "").strip()
    FHIR_SCOPE = os.environ.get("FHIR_SCOPE", "").strip()
    FHIR_ACCESS_TOKEN = os.environ.get("FHIR_ACCESS_TOKEN", "").strip()
    # Public origin for building jwks_uri (or set PORTAL_JWKS_URI directly)
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip()
    PORTAL_JWKS_URI = os.environ.get("PORTAL_JWKS_URI", "").strip()
    PORTAL_JWKS_JSON = os.environ.get("PORTAL_JWKS_JSON", "").strip()
    PORTAL_JWT_PRIVATE_KEY = os.environ.get("PORTAL_JWT_PRIVATE_KEY", "").strip()
    PORTAL_JWT_PRIVATE_KEY_PATH = os.environ.get(
        "PORTAL_JWT_PRIVATE_KEY_PATH", ""
    ).strip()
    PORTAL_JWT_KID = os.environ.get("PORTAL_JWT_KID", "").strip()
    PORTAL_JWT_ALG = os.environ.get("PORTAL_JWT_ALG", "RS384").strip() or "RS384"


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

LISA_BIO = [
    (
        "Hi, I'm Lisa—a Southern girl at heart with a deep commitment to nursing, "
        "patient-centered care, and serving others. While the South will always be "
        "home, my journey has taken me across many places and communities that have "
        "shaped both my practice and my perspective, strengthening my appreciation "
        "for diverse cultures, resilience, and the importance of meeting patients "
        "where they are."
    ),
    (
        "I am a proud graduate of Florida Atlantic University, where I earned my "
        "Bachelor of Science in Nursing, and Duke University, where I completed my "
        "Master of Science in Nursing and became a Family Nurse Practitioner. My "
        "seven years in the Duke Emergency Department were foundational in my "
        "development as a clinician—refining my assessment skills, strengthening my "
        "clinical judgment, and deepening my commitment to compassionate, "
        "evidence-based care in high-acuity settings."
    ),
    (
        "Today, I serve as a Family Nurse Practitioner in rural North Carolina, "
        "caring for patients and families across Sampson, Johnston, Wayne, and "
        "Duplin counties. At StartHere Patient Advocacy, I bring that same focus "
        "on prevention, chronic disease management, family engagement, and health "
        "education—building trust, listening closely, and partnering with patients "
        "and families in their care. Words I live by: \"The best way to find yourself "
        "is to lose yourself in the service of others.\""
    ),
]

INFO_EMAIL = os.environ.get(
    "CONTACT_INFO_EMAIL", "info@startherepatientadvocacy.com"
)
ORG_PHONE = os.environ.get("CONTACT_ORG_PHONE", "919-583-6484")

CONTACTS = [
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
    {
        "name": "Lisa Lafata",
        "slug": "lisa-lafata",
        "credentials": "MSN, FNP",
        "title": "Healthcare Advisor",
        "email": os.environ.get(
            "CONTACT_LISA_EMAIL", "lrldrn@yahoo.com"
        ),
        "phone": os.environ.get("CONTACT_LISA_PHONE", ""),
        "image": "lisa-lafata.png",
        "bio": LISA_BIO,
    },
    {
        "name": "Dawn Criswell",
        "slug": "dawn-criswell",
        "credentials": "MS, RHIA, FAHIMA",
        "title": "Patient Advocate",
        "email": os.environ.get(
            "CONTACT_DAWN_EMAIL", "Dawn.Criswell@startherepatientadvocacy.com"
        ),
        "phone": os.environ.get("CONTACT_DAWN_PHONE", ""),
        "image": "dawn-criswell.png",
        "bio": DAWN_BIO,
    },
]

SERVICE_CHOICES = [
    ("er-admittance", "ER Visit"),
    ("in-hospital", "Inpatient Stay"),
    ("discharge", "Discharge Support – Patient Advocacy"),
    ("followup", "After Encounter 10/20/30 Days Followup"),
    ("outpatient-procedure", "OutPatient Procedure Advocacy"),
]

SERVICE_LABELS = dict(SERVICE_CHOICES)

# Services with dedicated public intake forms (endpoint name for url_for).
# Generic Service Request redirects to these so service-specific metadata is captured.
SERVICE_INTAKE_ENDPOINTS = {
    "er-admittance": "client_patient.er_visit_request",
    "outpatient-procedure": "client_patient.outpatient_procedure_request",
}

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
