"""Drop and recreate all database tables."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db

DB_PATH = PROJECT_ROOT / 'instance' / 'eduscore.db'


def rebuild():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f'Removed {DB_PATH}')

    app = create_app()
    with app.app_context():
        db.create_all()
        print('Database recreated with new schema.')


if __name__ == '__main__':
    rebuild()
