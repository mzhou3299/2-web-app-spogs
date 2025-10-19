from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    course = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def to_dict(self):
    return {
        "id": self.id,
        "title": self.title,
        "course": self.course or "",
        "notes": self.notes or "",
        "due_date": self.due_date.isoformat(),
        "completed": self.completed,
        "created_at": self.created_at.isoformat(),
        "updated_at": self.updated_at.isoformat(),
    }
