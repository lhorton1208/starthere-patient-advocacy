from config import CONTACTS
from models import Advocate, Company, LookupList, db


COMPANY_NAME = "StartHere Patient Advocacy"

ACCOUNT_TYPES = [
    ("Client Receivable", "account_type", "Amounts owed by clients for advocacy services"),
    ("Service Revenue", "account_type", "Revenue from patient advocacy services"),
    ("Operating Expense", "account_type", "General operating expenses"),
]


def seed_database():
    company = Company.query.filter_by(name=COMPANY_NAME).first()
    if not company:
        company = Company(name=COMPANY_NAME)
        db.session.add(company)
        db.session.flush()

    for name, list_type, description in ACCOUNT_TYPES:
        exists = LookupList.query.filter_by(name=name, list_type=list_type).first()
        if not exists:
            db.session.add(
                LookupList(name=name, list_type=list_type, description=description)
            )

    for contact in CONTACTS:
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
            advocate.title = contact.get("title")
            if contact.get("email"):
                advocate.email = contact["email"]
            if contact.get("phone"):
                advocate.phone = contact["phone"]

    db.session.commit()
    return company
