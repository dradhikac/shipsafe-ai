# End-to-End Demo Flow — ShipSafe AI V2

## Overview
This document outlines the end-to-end demonstration flow for ShipSafe AI V2, showcasing continuous GitHub monitoring, parallel specialist agent analysis, live release gate evaluation, and verified remediation.

---

## Demo Script

### Step 1: Initialize System
1. Initialize local SQLite database and register the example CareHub repository (`examples/carehub`).
2. Launch FastAPI service on port 8000:
   ```bash
   python -m uvicorn api.app:app --port 8000
   ```
3. Launch the background analysis worker:
   ```bash
   python -m worker.worker
   ```
4. Launch the Streamlit DevSecOps Console on port 8501:
   ```bash
   streamlit run streamlit_app.py --server.port 8501
   ```

### Step 2: Trigger Webhook Simulation
Run the webhook simulator to emulate a developer pushing a high-risk change:
```bash
python scripts/simulate_webhook.py --event push --repo examples/carehub --branch feature/billing-v2
```
- Webhook arrives at `/webhooks/github` with cryptographic signature.
- Fast acknowledgment returns HTTP 202 Accepted.
- Analysis job enqueued with unique `delivery_id`.

### Step 3: Worker Execution & Parallel Agent Analysis
- The worker claims the job, checks out the commit, and executes the Deterministic Evidence Engine:
  - Discovers Python / Flask structure, models, migrations, and pytest test suite.
  - Runs tests deterministically; captures test failures.
  - Extracts git diff and modified symbols.
  - Redacts sensitive secrets.
- Worker sends Evidence Pack in parallel to the five specialist agents:
  1. Change Impact Agent
  2. Test Gap Agent
  3. Security Agent
  4. Requirements & API Agent
  5. Database & Dependency Agent
- Release Synthesizer cross-references findings with actual source files and calculates gate status: **BLOCKED**.

### Step 4: Streamlit DevSecOps Console Review
1. Open `http://localhost:8501`.
2. **Overview**: Shows repository status card flagged with `BLOCKED` badge.
3. **Live Events**: Displays real-time timeline of webhook arrival and agent execution stages.
4. **Findings**: Shows categorized, verified findings with exact line numbers and code snippets.
5. **Impact Map**: Graph visualization connecting commits -> files -> components -> tests.
6. **Requirements**: Shows R001–R005 traceability table with requirement status.
7. **Release Simulation**: Blast radius and regression path breakdown.

### Step 5: Remediation & Recheck
1. Navigate to **Remediation** tab in Streamlit.
2. Review proposed unified remediation patch.
3. Click **[ APPLY PATCH ]**.
4. The system:
   - Applies patch safely.
   - Re-runs pytest suite.
   - Re-runs agent analysis.
   - Verifies all blockers resolved.
5. Console updates gate status from `BLOCKED` to `READY`.
