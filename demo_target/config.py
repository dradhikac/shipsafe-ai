"""Configuration for CareHub Appointment Service."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.environ.get("CAREHUB_DB", os.path.join(BASE_DIR, "carehub.db"))
TESTING = False
DEBUG = False
