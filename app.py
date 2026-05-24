import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, url_for

from config import CONTACTS, Config, INSTANCE_DIR
from forms import PatientInfoForm
from models import PatientSubmission, db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.now().year}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/services/er-admittance")
    def er_admittance():
        return render_template("services/er_admittance.html")

    @app.route("/services/in-hospital-visits")
    def in_hospital_visits():
        return render_template("services/in_hospital_visits.html")

    @app.route("/services/discharge-support")
    def discharge_support():
        return render_template("services/discharge_support.html")

    @app.route("/services/after-encounter-followup")
    def after_encounter_followup():
        return render_template("services/after_encounter_followup.html")

    @app.route("/client/patient-info", methods=["GET", "POST"])
    def patient_info():
        form = PatientInfoForm()
        if form.validate_on_submit():
            submission = PatientSubmission(
                patient_name=form.patient_name.data.strip(),
                contact_name=form.contact_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip().lower(),
                service=form.service.data,
                hospital=(form.hospital.data or "").strip() or None,
                notes=(form.notes.data or "").strip() or None,
            )
            db.session.add(submission)
            db.session.commit()
            flash(
                "Thank you! Your request has been submitted. A member of our team will contact you soon.",
                "success",
            )
            return redirect(url_for("patient_info"))

        return render_template("client/patient_info.html", form=form)

    @app.route("/client/hipaa-forms")
    def hipaa_forms():
        return render_template("client/hipaa_forms.html")

    @app.route("/contacts")
    def contacts():
        return render_template("contacts.html", contacts=CONTACTS)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
