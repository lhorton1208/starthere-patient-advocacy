from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class PatientSubmission(db.Model):
    __tablename__ = "patient_submissions"

    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    service = db.Column(db.String(100), nullable=False)
    hospital = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<PatientSubmission {self.id}: {self.patient_name}>"
