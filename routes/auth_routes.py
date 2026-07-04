from urllib.parse import urlparse

from auth import (
    admin_required,
    authenticate,
    employee_required,
    get_current_advocate,
    login_advocate,
    logout_advocate,
)
from flask import Blueprint, flash, redirect, render_template, request, url_for
from forms import AdvocateLoginForm, ChangePasswordForm, LoginForm
from models import Advocate, db
from sqlalchemy.exc import IntegrityError

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_advocate() is not None:
        return redirect(url_for("encounters.list_encounters"))

    form = LoginForm()
    if form.validate_on_submit():
        advocate = authenticate(form.username.data, form.password.data)
        if advocate is None:
            flash("Invalid username or password.", "error")
        else:
            login_advocate(advocate)
            flash(f"Welcome back, {advocate.name}.", "success")
            next_url = _safe_next_url(request.args.get("next"))
            return redirect(next_url or url_for("encounters.list_encounters"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
def logout():
    logout_advocate()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@auth_bp.route("/account/password", methods=["GET", "POST"])
@employee_required
def change_password():
    advocate = get_current_advocate()
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not advocate.check_password(form.current_password.data):
            flash("Current password is incorrect.", "error")
        else:
            advocate.set_password(form.new_password.data)
            db.session.commit()
            flash("Your password has been updated.", "success")
            return redirect(url_for("encounters.list_encounters"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/staff/logins")
@admin_required
def manage_logins():
    advocates = Advocate.query.order_by(Advocate.name).all()
    return render_template("staff/logins/list.html", advocates=advocates)


@auth_bp.route("/staff/logins/<int:advocate_id>", methods=["GET", "POST"])
@admin_required
def edit_login(advocate_id):
    advocate = Advocate.query.get_or_404(advocate_id)
    form = AdvocateLoginForm()
    if request.method == "GET" and advocate.username:
        form.username.data = advocate.username
        form.is_admin.data = advocate.is_admin

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        password = (form.password.data or "").strip()
        confirm = (form.confirm_password.data or "").strip()

        if not advocate.has_login and not password:
            flash("Password is required when creating a new login.", "error")
        elif password and password != confirm:
            flash("Passwords must match.", "error")
        else:
            existing = Advocate.query.filter(
                Advocate.username == username,
                Advocate.id != advocate.id,
            ).first()
            if existing:
                flash("That username is already in use.", "error")
            else:
                advocate.username = username
                if password:
                    advocate.set_password(password)
                advocate.is_admin = bool(form.is_admin.data)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Could not save login. Please try again.", "error")
                else:
                    flash(f"Login saved for {advocate.name}.", "success")
                    return redirect(url_for("auth.manage_logins"))

    if request.method == "POST" and request.form.get("action") == "remove":
        advocate.clear_login()
        db.session.commit()
        flash(f"Login removed for {advocate.name}.", "success")
        return redirect(url_for("auth.manage_logins"))

    return render_template(
        "staff/logins/form.html",
        form=form,
        advocate=advocate,
    )
