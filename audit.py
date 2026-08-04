"""PHI access auditing — who accessed what, when, and how (no PHI values)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import has_request_context, request
from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Actions align with SQL-style audit terminology.
ACTION_SELECT = "SELECT"
ACTION_INSERT = "INSERT"
ACTION_UPDATE = "UPDATE"
ACTION_DELETE = "DELETE"

_PHI_TABLE_BY_CLASS_NAME = {
    "Patient": "patients",
    "Client": "clients",
    "Encounter": "encounters",
    "Note": "notes",
    "PatientMedication": "patient_medications",
    "PatientRelationship": "patient_relationships",
    "Account": "accounts",
    "Billing": "billings",
    "Invoice": "invoices",
    "InvoiceItem": "invoice_items",
    "TimeCard": "time_cards",
}

# Attribute names that are identifiers (safe to mention) vs content (never store values).
_SKIP_ATTRS = frozenset(
    {
        "password_hash",
        "created_at",
        "updated_at",
        "metadata",
        "registry",
        "query",
        "query_class",
    }
)

_listeners_registered = False


def _request_meta() -> dict[str, Optional[str]]:
    if not has_request_context():
        return {"request_method": None, "request_path": None, "ip_address": None}
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = (forwarded.split(",")[0].strip() if forwarded else None) or request.remote_addr
    path = request.full_path if request.query_string else request.path
    if path.endswith("?"):
        path = path[:-1]
    return {
        "request_method": request.method,
        "request_path": (path or "")[:500],
        "ip_address": (ip or "")[:64] if ip else None,
    }


def _current_actor() -> dict[str, Any]:
    try:
        from auth import get_current_advocate

        advocate = get_current_advocate()
    except Exception:
        advocate = None
    if not advocate:
        return {
            "advocate_id": None,
            "actor_username": None,
            "actor_name": "system/public",
        }
    return {
        "advocate_id": advocate.id,
        "actor_username": (advocate.username or "")[:64] or None,
        "actor_name": (advocate.name or advocate.username or "")[:200] or None,
    }


def _table_for(obj: Any) -> Optional[str]:
    return _PHI_TABLE_BY_CLASS_NAME.get(type(obj).__name__)


def _patient_id_for(obj: Any) -> Optional[int]:
    cls = type(obj).__name__
    if cls == "Patient":
        return getattr(obj, "id", None)
    if hasattr(obj, "patient_id") and getattr(obj, "patient_id", None):
        return obj.patient_id
    if cls == "Client":
        return getattr(obj, "patient_id", None)
    if cls == "Billing":
        note = getattr(obj, "note", None)
        if note is not None:
            return getattr(note, "patient_id", None)
        note_id = getattr(obj, "note_id", None)
        if note_id:
            try:
                from models import Note

                note = Note.query.get(note_id)
                return note.patient_id if note else None
            except Exception:
                return None
    if cls == "Invoice":
        account = getattr(obj, "account", None)
        if account is not None:
            return getattr(account, "patient_id", None)
        account_id = getattr(obj, "account_id", None)
        if account_id:
            try:
                from models import Account

                account = Account.query.get(account_id)
                return account.patient_id if account else None
            except Exception:
                return None
    if cls == "InvoiceItem":
        invoice = getattr(obj, "invoice", None)
        if invoice is not None:
            return _patient_id_for(invoice)
    if cls == "TimeCard":
        encounter = getattr(obj, "encounter", None)
        if encounter is not None:
            return getattr(encounter, "patient_id", None)
        encounter_id = getattr(obj, "encounter_id", None)
        if encounter_id:
            try:
                from models import Encounter

                enc = Encounter.query.get(encounter_id)
                return enc.patient_id if enc else None
            except Exception:
                return None
    return None


def _client_id_for(obj: Any) -> Optional[int]:
    cls = type(obj).__name__
    if cls == "Client":
        return getattr(obj, "id", None)
    if cls == "Patient":
        return getattr(obj, "client_id", None)
    if cls == "Account":
        return getattr(obj, "client_id", None)
    if cls == "Invoice":
        account = getattr(obj, "account", None)
        if account is not None:
            return getattr(account, "client_id", None)
        account_id = getattr(obj, "account_id", None)
        if account_id:
            try:
                from models import Account

                account = Account.query.get(account_id)
                return account.client_id if account else None
            except Exception:
                return None
    if cls == "InvoiceItem":
        invoice = getattr(obj, "invoice", None)
        if invoice is not None:
            return _client_id_for(invoice)
    if hasattr(obj, "client_id") and getattr(obj, "client_id", None):
        return obj.client_id
    return None


def _changed_columns(obj: Any) -> list[str]:
    try:
        state = sa_inspect(obj)
    except Exception:
        return []
    changed: list[str] = []
    for attr in state.attrs:
        if attr.key in _SKIP_ATTRS:
            continue
        hist = attr.history
        if hist.has_changes():
            changed.append(attr.key)
    return sorted(changed)


def log_phi_access(
    action: str,
    table_name: str,
    *,
    record_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    client_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    """Persist one PHI access audit row. Never stores PHI field values."""
    from datetime import datetime, timezone

    from models import PhiAccessLog, db

    action = (action or "").strip().upper()
    table_name = (table_name or "").strip()
    if not action or not table_name:
        return

    actor = _current_actor()
    meta = _request_meta()
    payload = {
        "created_at": datetime.now(timezone.utc),
        "advocate_id": actor["advocate_id"],
        "actor_username": actor["actor_username"],
        "actor_name": actor["actor_name"],
        "action": action[:20],
        "table_name": table_name[:100],
        "record_id": record_id,
        "patient_id": patient_id,
        "client_id": client_id,
        "detail": (detail or "")[:500] if detail else None,
        "request_method": meta["request_method"],
        "request_path": meta["request_path"],
        "ip_address": meta["ip_address"],
    }

    try:
        # Independent connection so audit fails closed without rolling back clinical work,
        # and so SELECT logging on pure GETs is persisted immediately.
        with db.engine.begin() as conn:
            conn.execute(PhiAccessLog.__table__.insert().values(**payload))
    except Exception:
        logger.exception(
            "Failed to write PHI access audit log action=%s table=%s record_id=%s",
            action,
            table_name,
            record_id,
        )


def log_phi_select(
    table_name: str,
    *,
    record_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    client_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    log_phi_access(
        ACTION_SELECT,
        table_name,
        record_id=record_id,
        patient_id=patient_id,
        client_id=client_id,
        detail=detail,
    )


def log_phi_list(table_name: str, *, row_count: int, detail: Optional[str] = None) -> None:
    label = detail or f"list accessed ({row_count} row{'s' if row_count != 1 else ''})"
    log_phi_access(ACTION_SELECT, table_name, detail=label)


def _queue_write_event(
    session: Session,
    action: str,
    obj: Any,
    *,
    detail: Optional[str] = None,
) -> None:
    table = _table_for(obj)
    if not table:
        return
    pending = session.info.setdefault("phi_audit_pending", [])
    pending.append(
        {
            "action": action,
            "table_name": table,
            "record_id": getattr(obj, "id", None),
            "patient_id": _patient_id_for(obj),
            "client_id": _client_id_for(obj),
            "detail": detail,
        }
    )


def _on_after_flush(session: Session, flush_context) -> None:
    if session.info.get("skip_phi_audit"):
        return

    for obj in session.new:
        if type(obj).__name__ == "PhiAccessLog":
            continue
        _queue_write_event(session, ACTION_INSERT, obj)

    for obj in session.dirty:
        if type(obj).__name__ == "PhiAccessLog":
            continue
        if not session.is_modified(obj, include_collections=False):
            continue
        cols = _changed_columns(obj)
        detail = f"fields: {', '.join(cols)}" if cols else "record updated"
        _queue_write_event(session, ACTION_UPDATE, obj, detail=detail)

    for obj in session.deleted:
        if type(obj).__name__ == "PhiAccessLog":
            continue
        _queue_write_event(session, ACTION_DELETE, obj)


def _on_after_commit(session: Session) -> None:
    pending = session.info.pop("phi_audit_pending", [])
    for item in pending:
        log_phi_access(
            item["action"],
            item["table_name"],
            record_id=item.get("record_id"),
            patient_id=item.get("patient_id"),
            client_id=item.get("client_id"),
            detail=item.get("detail"),
        )


def _on_after_rollback(session: Session) -> None:
    session.info.pop("phi_audit_pending", None)


def register_audit_listeners() -> None:
    """Idempotent registration of SQLAlchemy write-session audit listeners."""
    global _listeners_registered
    if _listeners_registered:
        return
    event.listen(Session, "after_flush", _on_after_flush)
    event.listen(Session, "after_commit", _on_after_commit)
    event.listen(Session, "after_rollback", _on_after_rollback)
    _listeners_registered = True
