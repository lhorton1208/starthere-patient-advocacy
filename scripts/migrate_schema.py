"""
Idempotent schema migration for StartHere (SQLite + PostgreSQL).

Run: python scripts/migrate_schema.py
Or automatically on app startup via app.create_app().
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app import create_app
from models import db


NEW_COLUMNS = {
    "clients": {
        "first_name": "VARCHAR(255)",
        "last_name": "VARCHAR(255)",
        "middle_name": "VARCHAR(255)",
        "suffix": "VARCHAR(10)",
        "prefix": "VARCHAR(255)",
        "account_number": "VARCHAR(255)",
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
        "phone_number2": "VARCHAR(32)",
        "relationship_to_patient_id": "INTEGER",
        "patient_id": "INTEGER",
    },
    "patients": {
        "address": "VARCHAR(300)",
        "middle_name": "VARCHAR(255)",
        "prefix": "VARCHAR(32)",
        "suffix": "VARCHAR(32)",
        "last4_ssn": "VARCHAR(4)",
        "last_encounter_date": "DATE",
        "created_by": "VARCHAR(255)",
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
        "phone_mobile": "VARCHAR(32)",
        "phone_landline": "VARCHAR(32)",
        "mood": "VARCHAR(255)",
        "mental_state": "VARCHAR(255)",
        "patient_medications_id": "INTEGER",
        "intake_notes": "TEXT",
    },
    "advocates": {
        "first_name": "VARCHAR(255)",
        "middle_name": "VARCHAR(255)",
        "last_name": "VARCHAR(255)",
        "phone_mobile": "VARCHAR(32)",
        "phone_landline": "VARCHAR(32)",
        "address": "VARCHAR(300)",
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
    },
    "providers": {
        "first_name": "VARCHAR(255)",
        "middle_name": "VARCHAR(255)",
        "last_name": "VARCHAR(255)",
        "location_id": "INTEGER",
    },
    "hospitals": {
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
        "main_phone_number": "VARCHAR(255)",
    },
    "home_health_facilities": {
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
        "facility_phone_number": "VARCHAR(32)",
        "point_of_contact_name": "VARCHAR(255)",
        "point_of_contact_phone_number": "VARCHAR(32)",
    },
    "encounters": {},
    "notes": {
        "patient_id": "INTEGER",
        "advocate_id": "INTEGER",
        "description": "TEXT",
        "note_text": "TEXT",
        "note_datetime": "TIMESTAMP",
    },
    "accounts": {
        "billing_address": "VARCHAR(255)",
        "city": "VARCHAR(255)",
        "state": "VARCHAR(255)",
        "zip_code": "VARCHAR(255)",
        "payment_method": "VARCHAR(255)",
        "credit_card_last4": "VARCHAR(4)",
        "exp_date": "VARCHAR(16)",
        "last_payment_date": "DATE",
    },
    "invoices": {
        "invoice_sub_total": "NUMERIC(10, 2)",
        "tax": "NUMERIC(10, 2)",
        "invoice_total": "NUMERIC(10, 2)",
        "description": "VARCHAR(255)",
    },
    "invoice_items": {
        "line_item_total": "NUMERIC(10, 2)",
    },
}


def _table_exists(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspector.get_columns(table)}


def _add_column(table: str, column: str, col_type: str, *, is_pg: bool = False) -> None:
    if is_pg:
        stmt = (
            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {col_type}'
        )
    else:
        stmt = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'
    db.session.execute(text(stmt))
    db.session.commit()


def _dedupe_emails(table: str, email_col: str = "email") -> None:
    rows = db.session.execute(
        text(
            f"""
            SELECT {email_col}, array_agg(id ORDER BY id) AS ids
            FROM {table}
            WHERE {email_col} IS NOT NULL AND TRIM({email_col}) != ''
            GROUP BY LOWER(TRIM({email_col}))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    # SQLite fallback in separate branch below
    if rows:
        pass


def _dedupe_emails_sqlite(table: str) -> None:
    dupes = db.session.execute(
        text(
            f"""
            SELECT LOWER(TRIM(email)) AS em, GROUP_CONCAT(id) AS ids
            FROM {table}
            WHERE email IS NOT NULL AND TRIM(email) != ''
            GROUP BY LOWER(TRIM(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for em, ids_csv in dupes:
        ids = [int(x) for x in ids_csv.split(",")]
        for dup_id in ids[1:]:
            db.session.execute(
                text(f"UPDATE {table} SET email = email || '.dup' || :id WHERE id = :id"),
                {"id": dup_id},
            )
    db.session.commit()


def _dedupe_emails_postgres(table: str) -> None:
    dupes = db.session.execute(
        text(
            f"""
            SELECT LOWER(TRIM(email)) AS em, array_agg(id ORDER BY id) AS ids
            FROM {table}
            WHERE email IS NOT NULL AND TRIM(email) != ''
            GROUP BY LOWER(TRIM(email))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for _em, ids in dupes:
        for dup_id in ids[1:]:
            db.session.execute(
                text(
                    f"UPDATE {table} SET email = email || '.dup' || :id::text WHERE id = :id"
                ),
                {"id": dup_id},
            )
    db.session.commit()


def _backfill_names(inspector) -> None:
    if "clients" not in inspector.get_table_names():
        return
    client_cols = {c["name"] for c in inspector.get_columns("clients")}
    if "first_name" not in client_cols:
        return

    clients = db.session.execute(
        text("SELECT id, name, phone, email, address FROM clients")
    ).fetchall()
    for row in clients:
        cid, name, phone, email, address = row
        parts = (name or "").strip().split()
        first = parts[0] if parts else "Client"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        db.session.execute(
            text(
                """
                UPDATE clients SET
                  first_name = COALESCE(NULLIF(first_name, ''), :first),
                  last_name = COALESCE(NULLIF(last_name, ''), :last),
                  phone = COALESCE(phone, :phone),
                  email = COALESCE(email, :email),
                  address = COALESCE(address, :address),
                  name = COALESCE(NULLIF(name, ''), :full)
                WHERE id = :id
                """
            ),
            {
                "id": cid,
                "first": first,
                "last": last,
                "phone": phone,
                "email": email,
                "address": address,
                "full": name or f"{first} {last}".strip(),
            },
        )

    if "patients" not in inspector.get_table_names():
        db.session.commit()
        return

    patient_cols = {c["name"] for c in inspector.get_columns("patients")}
    if "client_id" not in patient_cols:
        db.session.commit()
        return

    patients = db.session.execute(
        text(
            "SELECT id, first_name, last_name, phone, email, date_of_birth, client_id FROM patients"
        )
    ).fetchall()
    for row in patients:
        pid, first, last, phone, email, dob, client_id = row
        db.session.execute(
            text(
                """
                UPDATE patients SET
                  phone_mobile = COALESCE(phone_mobile, phone),
                  phone_landline = COALESCE(phone_landline, phone),
                  created_by = COALESCE(created_by, 'migration'),
                  email = COALESCE(email, :email)
                WHERE id = :id
                """
            ),
            {"id": pid, "email": email},
        )
        db.session.execute(
            text("UPDATE clients SET patient_id = :pid WHERE id = :cid AND patient_id IS NULL"),
            {"pid": pid, "cid": client_id},
        )
    db.session.commit()


def _backfill_notes() -> None:
    db.session.execute(
        text(
            """
            UPDATE notes SET
              note_text = COALESCE(note_text, content),
              description = COALESCE(description, LEFT(content, 255)),
              note_datetime = COALESCE(note_datetime, created_at)
            WHERE note_text IS NULL OR description IS NULL OR note_datetime IS NULL
            """
        )
    )
    db.session.execute(
        text(
            """
            UPDATE notes n SET patient_id = e.patient_id
            FROM encounters e
            WHERE n.encounter_id = e.id AND n.patient_id IS NULL
            """
        )
    )
    db.session.commit()


def _backfill_notes_sqlite() -> None:
    db.session.execute(
        text(
            """
            UPDATE notes SET
              note_text = COALESCE(note_text, content),
              description = COALESCE(description, substr(content, 1, 255)),
              note_datetime = COALESCE(note_datetime, created_at)
            """
        )
    )
    db.session.execute(
        text(
            """
            UPDATE notes SET patient_id = (
              SELECT patient_id FROM encounters WHERE encounters.id = notes.encounter_id
            )
            WHERE encounter_id IS NOT NULL AND patient_id IS NULL
            """
        )
    )
    db.session.commit()


def _ensure_schema_migrations_table() -> None:
    db.session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              name VARCHAR(255) PRIMARY KEY,
              applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    db.session.commit()


def _purge_clients_and_patients(inspector) -> None:
    """Remove all clients, patients, and rows that depend on them."""
    from models import (
        Account,
        Billing,
        Client,
        Encounter,
        Invoice,
        InvoiceItem,
        Note,
        Patient,
        PatientMedication,
        PatientRelationship,
        TimeCard,
    )

    tables = set(inspector.get_table_names())

    if "billings" in tables:
        Billing.query.delete()
    if "invoice_items" in tables:
        InvoiceItem.query.delete()
    if "invoices" in tables:
        Invoice.query.delete()
    if "accounts" in tables:
        Account.query.delete()
    if "time_cards" in tables:
        TimeCard.query.filter(TimeCard.encounter_id.isnot(None)).delete(
            synchronize_session=False
        )
    if "notes" in tables:
        Note.query.delete()
    if "encounters" in tables:
        Encounter.query.delete()
    if "patient_relationships" in tables:
        PatientRelationship.query.delete()
    if "patients" in tables and "patient_medications" in tables:
        db.session.execute(text("UPDATE patients SET patient_medications_id = NULL"))
    if "patient_medications" in tables:
        PatientMedication.query.delete()
    if "clients" in tables:
        db.session.execute(text("UPDATE clients SET patient_id = NULL"))
    if "patients" in tables:
        Patient.query.delete()
    if "clients" in tables:
        Client.query.delete()
    db.session.commit()


def _purge_clients_and_patients_once(inspector) -> None:
    _ensure_schema_migrations_table()
    done = db.session.execute(
        text(
            "SELECT 1 FROM schema_migrations WHERE name = 'purge_clients_patients_v1'"
        )
    ).first()
    if done:
        return
    _purge_clients_and_patients(inspector)
    is_pg = db.engine.dialect.name in ("postgresql", "postgres")
    if is_pg:
        db.session.execute(
            text(
                """
                INSERT INTO schema_migrations (name)
                VALUES ('purge_clients_patients_v1')
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
    else:
        try:
            db.session.execute(
                text(
                    "INSERT INTO schema_migrations (name) VALUES ('purge_clients_patients_v1')"
                )
            )
        except Exception:
            db.session.rollback()
            return
    db.session.commit()
    print("Removed all existing clients and patients (one-time).")


def _ensure_accounts_have_client() -> None:
    orphan = db.session.execute(
        text("SELECT id FROM accounts WHERE client_id IS NULL LIMIT 1")
    ).first()
    if not orphan:
        return
    fallback = db.session.execute(text("SELECT id FROM clients ORDER BY id LIMIT 1")).first()
    if fallback:
        db.session.execute(
            text("UPDATE accounts SET client_id = :cid WHERE client_id IS NULL"),
            {"cid": fallback[0]},
        )
        db.session.commit()


def run_migrations(app=None) -> None:
    app = app or create_app(run_migrate=False)
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        is_sqlite = engine.dialect.name == "sqlite"
        is_pg = engine.dialect.name in ("postgresql", "postgres")

        db.create_all()

        for table, columns in NEW_COLUMNS.items():
            if not _table_exists(inspector, table):
                continue
            for column, col_type in columns.items():
                if not _column_exists(inspector, table, column):
                    _add_column(table, column, col_type, is_pg=is_pg)
                    inspector = inspect(engine)

        if is_sqlite:
            _dedupe_emails_sqlite("clients")
            _dedupe_emails_sqlite("patients")
        elif is_pg:
            _dedupe_emails_postgres("clients")
            _dedupe_emails_postgres("patients")

        _backfill_names(inspector)
        if "notes" in inspector.get_table_names():
            if is_pg:
                try:
                    _backfill_notes()
                except Exception:
                    db.session.rollback()
                    _backfill_notes_sqlite()
            else:
                _backfill_notes_sqlite()

        _purge_clients_and_patients_once(inspector)
        if "accounts" in inspector.get_table_names():
            _ensure_accounts_have_client()

        # Unique indexes (best-effort; skip if duplicates remain)
        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_email ON clients (email) WHERE email IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_email ON patients (email) WHERE email IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_client_id ON patients (client_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_patient_id ON clients (patient_id) WHERE patient_id IS NOT NULL",
        ]
        for stmt in indexes:
            try:
                db.session.execute(text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

        from seed import seed_database

        seed_database()
        print("Schema migration completed.")


if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as exc:
        print(f"Schema migration failed: {exc}", flush=True)
        raise SystemExit(1) from exc
