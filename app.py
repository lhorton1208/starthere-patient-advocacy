import os
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, send_from_directory, url_for
from whitenoise import WhiteNoise

from blog_content import ARTICLES, get_article
from config import BASE_DIR, CONTACTS, Config, INFO_EMAIL, INSTANCE_DIR, ORG_PHONE
from models import db
from routes.billing import billing_bp
from routes.client_patient import client_patient_bp
from routes.encounters import encounters_bp
from routes.entities import entities_bp
from routes.reports import reports_bp
from seed import seed_database


def create_app(config_class=Config, *, run_migrate=True):
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

    if run_migrate:
        with app.app_context():
            from scripts.migrate_schema import run_migrations

            run_migrations(app)

    @app.template_filter("static_image_exists")
    def static_image_exists(filename):
        if not filename:
            return False
        return os.path.isfile(os.path.join(static_dir, "images", filename))

    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.now().year,
            "info_email": INFO_EMAIL,
            "org_phone": ORG_PHONE,
            "blog_articles": ARTICLES,
        }

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/services/pricing")
    def pricing():
        return render_template("services/pricing.html")

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

    @app.route("/services/outpatient-procedure")
    def outpatient_procedure():
        return render_template("services/outpatient_procedure.html")

    @app.route("/client/patient-info")
    def patient_info_redirect():
        return redirect(url_for("client_patient.list_patients"))

    @app.route("/client/hipaa-forms")
    def hipaa_forms():
        return render_template("client/hipaa_forms.html")

    @app.route("/about")
    def about():
        advocates = [c for c in CONTACTS if c.get("bio")]
        return render_template("about.html", advocates=advocates)

    @app.route("/contacts")
    def contacts():
        return render_template("contacts.html", contacts=CONTACTS)

    @app.route("/blog")
    def blog_index():
        return render_template("blog/index.html", articles=ARTICLES)

    @app.route("/blog/<slug>")
    def blog_article(slug):
        article = get_article(slug)
        if article is None:
            abort(404)
        return render_template(f"blog/{slug}.html", article=article)

    @app.route("/static/images/starthere-logo-icon.png")
    def logo_asset():
        return send_from_directory(
            os.path.join(static_dir, "images"),
            "starthere-logo-icon.png",
            mimetype="image/png",
        )

    app.wsgi_app = WhiteNoise(app.wsgi_app, root=static_dir, prefix="static/")
    return app


# Gunicorn/Render entrypoint — run migrations on boot so schema stays current
# even when Render pre-deploy hooks are missing or fail.
app = create_app(run_migrate=os.environ.get("RUN_MIGRATE", "1") == "1")


if __name__ == "__main__":
    # macOS often binds AirPlay to localhost:5000; use 5001 locally.
    port = int(os.environ.get("PORT", 5001))
    create_app(run_migrate=True).run(debug=True, host="127.0.0.1", port=port)
