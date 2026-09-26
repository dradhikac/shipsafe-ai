"""Clear all runtime database records, recreate fresh schema, and remove managed repository clones."""

import os
import shutil
import stat
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shipsafe.database import engine, Base, init_db
from shipsafe.core.repo_manager import MANAGED_REPOS_DIR


def _remove_readonly(func, path, exc_info):
    """Clear the read-only bit and retry removal for Windows git files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def clear_runtime_data():
    print("[ShipSafe Clean] Clearing all runtime repositories and resetting clean schema...")
    try:
        # Drop all tables to eliminate legacy columns/schema drifts
        Base.metadata.drop_all(bind=engine)
        # Recreate all tables cleanly
        init_db()
        print("[ShipSafe Clean] Database tables reset with fresh schema (0 records).")
    except Exception as e:
        print(f"[ShipSafe Clean Error] Failed to reset database: {e}", file=sys.stderr)

    # Clear managed cloned repositories directory
    if os.path.isdir(MANAGED_REPOS_DIR):
        try:
            shutil.rmtree(MANAGED_REPOS_DIR, onerror=_remove_readonly)
            print(f"[ShipSafe Clean] Cleared managed repositories directory: {MANAGED_REPOS_DIR}")
        except Exception as e:
            print(f"[ShipSafe Clean Warning] Could not delete {MANAGED_REPOS_DIR}: {e}", file=sys.stderr)

    print("[ShipSafe Clean] Runtime environment is now completely clean (0 repositories connected).")


if __name__ == "__main__":
    clear_runtime_data()
