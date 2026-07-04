from functools import wraps

from flask import flash, redirect, request, session, url_for

SESSION_ADVOCATE_ID = "advocate_id"


def get_current_advocate():
    advocate_id = session.get(SESSION_ADVOCATE_ID)
    if not advocate_id:
        return None
    from models import Advocate

    advocate = Advocate.query.get(advocate_id)
    if advocate is None or not advocate.active or not advocate.has_login:
        session.pop(SESSION_ADVOCATE_ID, None)
        return None
    return advocate


def login_advocate(advocate) -> None:
    session[SESSION_ADVOCATE_ID] = advocate.id
    session.modified = True


def logout_advocate() -> None:
    session.pop(SESSION_ADVOCATE_ID, None)
    session.modified = True


def authenticate(username: str, password: str):
    from models import Advocate

    username = (username or "").strip().lower()
    if not username or not password:
        return None
    advocate = Advocate.query.filter(
        Advocate.username == username,
        Advocate.active.is_(True),
    ).first()
    if advocate is None or not advocate.check_password(password):
        return None
    return advocate


def employee_required(view):
    """Require an authenticated advocate for staff-only routes."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_advocate() is None:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Require an authenticated advocate with admin privileges."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        advocate = get_current_advocate()
        if advocate is None:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("auth.login", next=request.full_path))
        if not advocate.is_admin:
            flash("You do not have permission to access that page.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped
