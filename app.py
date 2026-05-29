import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, send_from_directory, url_for
from whitenoise import WhiteNoise

from config import BASE_DIR, CONTACTS, Config, INSTANCE_DIR
from forms import PatientInfoForm
from intake import create_intake_request
from models import db
from routes.billing import billing_bp
from routes.encounters import encounters_bp
from seed import seed_database


def create_app(config_class=Config):
    static_dir = os.path.join(BASE_DIR, "static")
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
    app.config.from_object(config_class)

    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)

    app.register_blueprint(encounters_bp)
    app.register_blueprint(billing_bp)

    with app.app_context():
        db.create_all()
        seed_database()

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
            create_intake_request(
                patient_name=form.patient_name.data.strip(),
                contact_name=form.contact_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip().lower(),
                service=form.service.data,
                hospital_name=(form.hospital.data or "").strip() or None,
                notes=(form.notes.data or "").strip() or None,
            )
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

    @app.route("/static/images/starthere-logo-icon.png")
    def logo_asset():
        return send_from_directory(
            os.path.join(static_dir, "images"),
            "starthere-logo-icon.png",
            mimetype="image/png",
        )

    app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_dir, prefix="static/")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
