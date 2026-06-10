"""Initialize the database for formal startup mode.

This script is intentionally safe:
- it does not delete existing data
- it only creates missing tables
- it ensures the default teacher account exists
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import User


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()

        teacher = User.query.filter_by(username='teacher').first()
        created = False
        if teacher is None:
            teacher = User(username='teacher', display_name='张老师', role='teacher')
            teacher.set_password('teacher123')
            db.session.add(teacher)
            db.session.commit()
            created = True

        print('Database initialized.')
        if created:
            print('Default teacher account created: teacher / teacher123')
        else:
            print('Default teacher account already exists.')


if __name__ == '__main__':
    init_db()
