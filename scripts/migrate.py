"""Run migrations to initialize the contributions SQLite database.

Usage (PowerShell):
  & .\venv\Scripts\Activate.ps1
  python scripts/migrate.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import init_db

if __name__ == '__main__':
    print('Initializing database...')
    init_db()
    print('Done. Database created/updated at', os.getenv('CONTRIB_DB', os.path.join(os.getcwd(), 'contributions.db')))
