"""Convenience runner for ShipSafe AI V2 local stack."""

import os
import subprocess
import sys
import time


def main():
    print("=" * 60)
    print("  ShipSafe AI V2 — Local Stack Launcher")
    print("=" * 60)

    # 1. Initialize and seed DB
    print("\n[Step 1/3] Initializing and seeding local database...")
    subprocess.run([sys.executable, "scripts/seed_demo.py"], check=True)

    print("\n[Step 2/3] Stack components:")
    print("  1. FastAPI Webhook API: uvicorn api.app:app --port 8000")
    print("  2. Background Worker:   python -m worker.worker")
    print("  3. Streamlit Console:   streamlit run streamlit_app.py --server.port 8501")

    print("\n[Step 3/3] Ready! To launch individual services, use separate terminals or run:")
    print("   Terminal 1: uvicorn api.app:app --reload --port 8000")
    print("   Terminal 2: python -m worker.worker")
    print("   Terminal 3: streamlit run streamlit_app.py --server.port 8501")
    print("\nTo simulate a GitHub webhook push:")
    print("   python scripts/simulate_webhook.py --event push --repo carehub-appointment-service")
    print("=" * 60)


if __name__ == "__main__":
    main()
