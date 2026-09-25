"""CareHub Appointment Service — Flask application factory."""

import os
import sys

# Allow sibling imports when running directly (python app.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify
import db as database
from routes.patients import patients_bp
from routes.doctors import doctors_bp
from routes.appointments import appointments_bp


def create_app(config_overrides=None):
    """Application factory.

    Pass config_overrides as a dict to customise settings, e.g. for testing.
    """
    app = Flask(__name__)

    # Defaults
    app.config["DATABASE"] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "carehub.db"
    )
    app.config["TESTING"] = False

    if config_overrides:
        app.config.update(config_overrides)

    database.init_app(app)

    # Blueprints
    app.register_blueprint(patients_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(appointments_bp)

    @app.get("/health")
    def health():
        return jsonify({
            "service": "CareHub Appointment Service",
            "status": "ok",
        }), 200

    # Initialise the schema on first request
    with app.app_context():
        database.init_db()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, port=5050)
