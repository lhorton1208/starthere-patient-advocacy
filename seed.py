from config import CONTACTS
from models import Advocate, Company, LookupList, RelationshipToPatient, db


COMPANY_NAME = "StartHere Patient Advocacy"

ACCOUNT_TYPES = [
    ("Client Receivable", "account_type", "Amounts owed by clients for advocacy services"),
    ("Service Revenue", "account_type", "Revenue from patient advocacy services"),
    ("Operating Expense", "account_type", "General operating expenses"),
]

RELATIONSHIP_TYPES = [
    ("Self", "Patient is the client", False, False),
    ("Spouse", "Spouse or partner", False, False),
    ("Son", "Son of patient", False, False),
    ("Daughter", "Daughter of patient", False, False),
    ("Parent", "Parent of patient", False, True),
    ("Child", "Child of patient", True, False),
    ("Sibling", "Sibling of patient", False, False),
    ("Other Family", "Other family member", False, False),
    ("Friend", "Friend of patient", False, False),
    ("Legal Guardian", "Legal guardian", True, False),
    ("Power of Attorney", "Power of attorney", False, True),
]


def seed_database():
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        company = Company(name=COMPANY_NAME)
        db.session.add(company)
        db.session.flush()

    for relationship, description, guardian, poa in RELATIONSHIP_TYPES:
        exists = RelationshipToPatient.query.filter_by(relationship=relationship).first()
        if not exists:
            db.session.add(
                RelationshipToPatient(
                    relationship=relationship,
                    description=description,
                    is_legal_guardian=guardian,
                    is_power_of_attorney=poa,
                )
            )

    for name, list_type, description in ACCOUNT_TYPES:
        exists = LookupList.query.filter_by(name=name, list_type=list_type).first()
        if not exists:
            db.session.add(
                LookupList(name=name, list_type=list_type, description=description)
            )

    for contact in CONTACTS:
        lookup_name = contact.get("legacy_name") or contact["name"]
        advocate = Advocate.query.filter_by(
            company_id=company.id, name=lookup_name
        ).first()
        if not advocate and lookup_name != contact["name"]:
            advocate = Advocate.query.filter_by(
                company_id=company.id, name=contact["name"]
            ).first()
        if not advocate:
            db.session.add(
                Advocate(
                    company_id=company.id,
                    name=contact["name"],
                    title=contact.get("title"),
                    email=contact.get("email") or None,
                    phone=contact.get("phone") or None,
                )
            )
        else:
            advocate.name = contact["name"]
            advocate.title = contact.get("title")
            if contact.get("email"):
                advocate.email = contact["email"]
            if contact.get("phone"):
                advocate.phone = contact["phone"]

    db.session.commit()
    return company
