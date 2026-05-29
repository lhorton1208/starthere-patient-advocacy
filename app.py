import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, send_from_directory, url_for
from whitenoise import WhiteNoise

from config import BASE_DIR, CONTACTS, Config, INSTANCE_DIR
from models import db
from routes.billing import billing_bp
from routes.client_patient import client_patient_bp
from routes.encounters import encounters_bp
from routes.entities import entities_bp
from routes.reports import reports_bp
from seed import seed_database


def create_app(config_class=Config):
    static_dir = os.path.join(BASE_DIR, "static")
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
    app.config.from_object(config_class)

    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)

    app.register_blueprint(encounters_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(entities_bp)
    app.register_blueprint(client_patient_bp)

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

    @app.route("/client/patient-info")
    def patient_info_redirect():
        return redirect(url_for("client_patient.list_patients"))

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
