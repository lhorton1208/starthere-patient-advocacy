from auth import employee_required
from flask import Blueprint, flash, redirect, render_template, url_for
from seed import COMPANY_NAME
from forms import (
    AdvocateEntityForm,
    HomeHealthFacilityForm,
    HospitalForm,
    RelationshipToPatientForm,
)
from models import (
    Advocate,
    Company,
    HomeHealthFacility,
    Hospital,
    RelationshipToPatient,
    db,
)

entities_bp = Blueprint("entities", __name__, url_prefix="/entities")


def _company():
    return Company.query.filter_by(name=COMPANY_NAME).first()


@entities_bp.route("/hospitals")
@employee_required
def list_hospitals():
    rows = Hospital.query.order_by(Hospital.name).all()
    return render_template("staff/entities/hospital_list.html", rows=rows)


@entities_bp.route("/hospitals/new", methods=["GET", "POST"])
@entities_bp.route("/hospitals/<int:item_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_hospital(item_id=None):
    item = Hospital.query.get(item_id) if item_id else None
    form = HospitalForm(obj=item)
    if form.validate_on_submit():
        hospital = item or Hospital()
        hospital.name = form.name.data.strip()
        hospital.address = (form.address.data or "").strip() or None
        hospital.phone = (form.phone.data or "").strip() or None
        if not item:
            db.session.add(hospital)
        db.session.commit()
        flash("Hospital saved.", "success")
        return redirect(url_for("entities.list_hospitals"))
    return render_template(
        "staff/entities/hospital_form.html",
        form=form,
        title="Edit Hospital" if item else "New Hospital",
    )


@entities_bp.route("/advocates")
@employee_required
def list_advocates():
    rows = Advocate.query.order_by(Advocate.name).all()
    return render_template("staff/entities/advocate_list.html", rows=rows)


@entities_bp.route("/advocates/new", methods=["GET", "POST"])
@entities_bp.route("/advocates/<int:item_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_advocate(item_id=None):
    company = _company()
    item = Advocate.query.get(item_id) if item_id else None
    form = AdvocateEntityForm(obj=item)
    if item:
        form.active.data = "1" if item.active else "0"
    if form.validate_on_submit():
        advocate = item or Advocate(company_id=company.id)
        advocate.name = form.name.data.strip()
        advocate.title = (form.title.data or "").strip() or None
        advocate.phone = (form.phone.data or "").strip() or None
        advocate.email = (form.email.data or "").strip() or None
        advocate.active = form.active.data == "1"
        if not item:
            db.session.add(advocate)
        db.session.commit()
        flash("Advocate saved.", "success")
        return redirect(url_for("entities.list_advocates"))
    return render_template(
        "staff/entities/advocate_form.html",
        form=form,
        title="Edit Advocate" if item else "New Advocate",
    )


@entities_bp.route("/home-care")
@employee_required
def list_home_care():
    rows = HomeHealthFacility.query.order_by(HomeHealthFacility.name).all()
    return render_template("staff/entities/home_care_list.html", rows=rows)


@entities_bp.route("/home-care/new", methods=["GET", "POST"])
@entities_bp.route("/home-care/<int:item_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_home_care(item_id=None):
    item = HomeHealthFacility.query.get(item_id) if item_id else None
    form = HomeHealthFacilityForm(obj=item)
    if form.validate_on_submit():
        facility = item or HomeHealthFacility()
        facility.name = form.name.data.strip()
        facility.address = (form.address.data or "").strip() or None
        facility.phone = (form.phone.data or "").strip() or None
        if not item:
            db.session.add(facility)
        db.session.commit()
        flash("Home care facility saved.", "success")
        return redirect(url_for("entities.list_home_care"))
    return render_template(
        "staff/entities/home_care_form.html",
        form=form,
        title="Edit Home Care Facility" if item else "New Home Care Facility",
    )


@entities_bp.route("/relationships")
@employee_required
def list_relationships():
    rows = RelationshipToPatient.query.order_by(
        RelationshipToPatient.relationship
    ).all()
    return render_template("staff/entities/relationship_list.html", rows=rows)


@entities_bp.route("/relationships/new", methods=["GET", "POST"])
@entities_bp.route("/relationships/<int:item_id>/edit", methods=["GET", "POST"])
@employee_required
def edit_relationship(item_id=None):
    item = RelationshipToPatient.query.get(item_id) if item_id else None
    form = RelationshipToPatientForm(obj=item)
    if item:
        form.is_legal_guardian.data = "1" if item.is_legal_guardian else "0"
        form.is_power_of_attorney.data = "1" if item.is_power_of_attorney else "0"
    if form.validate_on_submit():
        record = item or RelationshipToPatient()
        record.relationship = form.relationship.data.strip()
        record.description = form.description.data.strip()
        record.is_legal_guardian = form.is_legal_guardian.data == "1"
        record.is_power_of_attorney = form.is_power_of_attorney.data == "1"
        if not item:
            db.session.add(record)
        db.session.commit()
        flash("Relationship saved.", "success")
        return redirect(url_for("entities.list_relationships"))
    return render_template(
        "staff/entities/relationship_form.html",
        form=form,
        title="Edit Relationship" if item else "New Relationship",
    )
