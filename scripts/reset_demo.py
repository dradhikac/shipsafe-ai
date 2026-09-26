#!/usr/bin/env python3
"""Reset the CareHub demo target to the clean baseline state.

This script is the counterpart to apply_demo_release.py.  It restores all
demo_target/ files that were modified by the demo to their committed baseline
state and verifies that the baseline test suite passes afterwards.

Usage:
    python scripts/reset_demo.py

Safety rules enforced:
  - Uses `git checkout` on only the specific demo_target files — never a
    repository-wide destructive reset.
  - Does not touch ShipSafe engine files (shipsafe/).
  - Removes only the generated artifacts created during the demo (the
    migrations/002_add_urgency_level.sql file is NOT present because the demo
    scenario demonstrates its ABSENCE — nothing to clean up there).
  - Reports the restored files and then runs pytest to confirm the baseline.
"""

import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files modified by the demo release that must be restored
DEMO_FILES = [
    "demo_target/services/notification_service.py",
    "demo_target/models.py",
    "demo_target/db.py",
    "demo_target/routes/appointments.py",
    "demo_target/tests/test_notifications.py",
    "demo_target/tests/test_appointments.py",
]

# Generated artifacts to remove (if present)
GENERATED_ARTIFACTS = [
    # None: the demo does NOT generate any new files inside demo_target/.
    # migrations/002_add_priority_critical.sql is intentionally ABSENT — that
    # is the R003 finding.  The 001_initial_schema.sql is a committed baseline
    # artifact and must NOT be removed.
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd, cwd=None, check=False):
    result = subprocess.run(
        cmd, cwd=cwd or REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if check and result.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def _abort(message):
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("ShipSafe Demo — Reset to Clean Baseline")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Restore modified demo_target files via git checkout
    # ------------------------------------------------------------------
    print("\n[1/3] Restoring demo_target files to baseline commit...")
    r = _run(["git", "checkout", "HEAD", "--"] + DEMO_FILES)
    if r.returncode != 0:
        _abort(
            f"git checkout failed:\n{r.stderr}\n"
            "Ensure HEAD points to the baseline commit or run:\n"
            "  git checkout 5f95cd16 -- " + " ".join(DEMO_FILES)
        )
    for f in DEMO_FILES:
        print(f"  RESTORED  {f}")

    # ------------------------------------------------------------------
    # Step 2: Remove generated artifacts (if any were created)
    # ------------------------------------------------------------------
    print("\n[2/3] Removing demo-generated artifacts...")
    removed = 0
    for artifact in GENERATED_ARTIFACTS:
        full = os.path.join(REPO_ROOT, artifact)
        if os.path.exists(full):
            os.remove(full)
            print(f"  REMOVED   {artifact}")
            removed += 1
    if removed == 0:
        print("  (no generated artifacts to remove)")

    # ------------------------------------------------------------------
    # Step 3: Verify the baseline test suite passes
    # ------------------------------------------------------------------
    print("\n[3/3] Verifying baseline tests pass...")
    r = _run([
        sys.executable, "-m", "pytest",
        "demo_target/tests/", "-q", "--tb=short"
    ])
    output_lines = (r.stdout + r.stderr).splitlines()
    # Print last 15 lines of pytest output
    for line in output_lines[-15:]:
        print(f"  {line}")

    if r.returncode != 0:
        print("\nWARNING: Baseline tests did not pass after reset.", file=sys.stderr)
        print("Check the output above for failures.", file=sys.stderr)
        sys.exit(1)

    # Check for passing summary in output
    combined = r.stdout + r.stderr
    if "passed" in combined and "failed" not in combined:
        print("\n  BASELINE VERIFIED — all tests pass.")
    else:
        print("\n  WARNING: unexpected test output. Review above.", file=sys.stderr)
        sys.exit(1)

    print("""
Reset complete.
  - demo_target/ files restored to baseline commit (5f95cd1)
  - ShipSafe engine files untouched
  - Baseline tests pass

To re-apply the demo release:
  python scripts/apply_demo_release.py
""")


if __name__ == "__main__":
    main()
