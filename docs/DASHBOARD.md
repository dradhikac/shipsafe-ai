# ShipSafe AI — Web Dashboard & REST API Specification

ShipSafe AI is an Agentic Release & Regression Guardian. The dashboard provides an enterprise DevSecOps web interface that renders the full deterministic release analysis pipeline into an intuitive, evidence-backed interface for developers and release engineers.

---

## 1. Dashboard Architecture

The dashboard is engineered to be lightweight, self-contained, and deterministic:

```
shipsafe/web/
├── __init__.py          — Web package initialization
├── app.py               — Flask application factory, data store, routes, and REST API
├── templates/
│   ├── index.html       — Main DevSecOps dashboard UI
│   └── report_detail.html — Accessible report inspector / JSON viewer
└── static/
    ├── css/
    │   └── style.css    — Dark graphite DevSecOps design system
    └── js/
        └── app.js       — Client filtering, modal detail drawer, copy helpers, and live refresh
```

### Technology Constraints Enforced
- **Backend**: Python 3.11 + Flask + Jinja2 templates.
- **Frontend**: Vanilla HTML5, CSS3, and modern JavaScript (ES6+).
- **Strictly Self-Contained**: No React, Vue, Angular, webpack, npm, external CDNs, or external AI APIs.
- **Zero Hallucination / Mock Data**: All data served by the UI is read directly from repository report artifacts generated in previous phases.

---

## 2. Visual Design & Theme

- **Visual Direction**: High-contrast dark graphite theme (`#090d16` background with technical grid pattern).
- **Status Accents**:
  - `RELEASE BLOCKED` / `CRITICAL`: Red (`#ef4444`) with soft ambient glow.
  - `CONFLICTED` / `WARNING`: Amber (`#f59e0b`).
  - `COMPLIANT` / `PASS`: Emerald Green (`#10b981`).
  - `ACCENTS`: Restrained Cyber Cyan (`#38bdf8`) and Slate Blue (`#3b82f6`).
- **Typography**: Clean monospace code styling for IDs, file paths, and test commands; modern system sans-serif for high legibility.
- **Card-Based Hierarchy**: Clear sections for Executive Hero, KPIs, IBM Bob Agents, Traceability Matrix, Findings Table, Impact Simulation, Measurement Comparisons, Remediation Plan, and Audit Trail.

---

## 3. JSON Data Sources

The dashboard dynamically ingests and serves data from 10 authoritative JSON files:

| Dashboard Section | Source Artifact | Description |
|---|---|---|
| **Top Bar & Executive Hero** | `reports/latest_release_report.json` | Release status (`RELEASE_READY`), timestamp, finding severity counts. |
| **KPI Metrics** | `reports/comparison.json` | Baseline vs Bad Release vs Post-Remediation metrics (38 → 31 → 42 tests, 98% → 96% → 98% cov, 0 findings). |
| **IBM Bob 2.0 Agents** | `reports/agents/*.json` (5 files) | Individual subagent reports (Impact, Test Gap, Security, Contract, Database). |
| **Requirement Traceability** | `reports/traceability.json` | R001–R005 implementation, validation tests, and R003 resolution data. |
| **Findings Table** | `reports/latest_release_report.json` | Authoritative list of findings with severity, status, and remediation notes. |
| **Release Simulation** | `reports/release_simulation.json` | Affected components, workflows, regression flow paths, highest-risk component. |
| **Release Measurement** | `reports/comparison.json` | Baseline vs Bad Release vs Post-Remediation state cards with verified metrics. |
| **Remediation Plan** | `reports/remediation_plan.json` | Ordered items (P1–P5) with validation commands and verification status. |
| **Audit Trail** | All 10 report files | Real-time file existence, size, and readable detail routes. |

---

## 4. REST API Endpoints

All endpoints return structured JSON with standard HTTP status codes:

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/overview` | `GET` | High-level status, repository details, finding counts, and evidence statement. |
| `GET /api/agents` | `GET` | Summary of all five IBM Bob 2.0 analysis agents and attribution. |
| `GET /api/requirements` | `GET` | R001–R005 requirement compliance, status, and associated findings. |
| `GET /api/findings` | `GET` | 22 synthesized findings. Supports query filtering: `?severity=CRITICAL`, `?requirement=R004`, `?agent=sec`. |
| `GET /api/traceability` | `GET` | Full requirement-to-code traceability matrix including R003 conflict. |
| `GET /api/simulation` | `GET` | Impact simulation, affected workflows, and visual regression paths. |
| `GET /api/remediation` | `GET` | Prioritized remediation plan sequence (P1: R004 to P5: R005). |
| `GET /api/comparison` | `GET` | Baseline vs bad-release comparison metrics and post-remediation status. |
| `GET /api/report/<type>` | `GET` | Raw JSON of a specific report (e.g. `synthesis`, `traceability`, `agent-security`). |
| `POST /api/refresh` | `POST` | Invalidates cached memory reports and reloads artifacts from disk. |

---

## 5. IBM Bob 2.0 Attribution & Historical Integrity

The dashboard prominently credits IBM Bob 2.0:
- Dedicated section: **"IBM Bob 2.0 Analysis Agents"** showing the five independent subagent investigations.
- Attribution label: *"Historical analysis artifacts generated by IBM Bob 2.0"*.
- The five reports under `reports/agents/` are treated as read-only historical evidence.
- The UI makes it visually clear that the investigations occurred across parallel workstreams prior to synthesis.

---

## 6. R003 Conflict Special Visual Treatment

The dashboard does not hide or obscure the design disagreement regarding R003:
- Sourced directly from `reports/traceability.json`.
- Displays a dedicated **CONFLICTED** alert card showing:
  1. **Database Analyst Recommendation**: *"Create migrations/002_add_priority_critical.sql to add CHECK constraint for 'critical'."*
  2. **Contract / Impact Analyst Recommendation**: *"Remove unauthorized 'critical' priority; R003 specifies only ('normal', 'high', 'emergency')."*
  3. **Deterministic Synthesis Resolution**: *"Requirement specification takes precedence during remediation planning. Reject Migration 002."*

---

## 7. Refresh Behavior

- Clicking the **"REFRESH ANALYSIS DATA"** button triggers `POST /api/refresh`.
- Clears the in-memory cache in `DataStore`.
- Reloads all 10 JSON artifacts from disk.
- Does **not** re-run subagents, mutate application code, or trigger background builds.

---

## 8. Error & Empty States Handling

- **Missing Report File**: Returns HTTP 404 with structured JSON:
  ```json
  {
    "error": "Report artifact not found: reports/...",
    "status": "NOT_FOUND"
  }
  ```
- **Corrupted / Invalid JSON**: Returns HTTP 500 with structured JSON:
  ```json
  {
    "error": "Invalid JSON in report '...': ...",
    "status": "INVALID_JSON"
  }
  ```
- **Post-Remediation Unavailability**: Rendered cleanly in the UI as `STATUS: NOT AVAILABLE` without zero-coercion or projected estimates.

---

## 9. Local Startup Command

To launch the ShipSafe AI dashboard locally:

```bash
# Default: runs on http://127.0.0.1:5000
python -m shipsafe.web.app

# Custom port or host:
SHIPSAFE_PORT=8080 python -m shipsafe.web.app
```

Once running, navigate to `http://127.0.0.1:5000` in any modern web browser.
