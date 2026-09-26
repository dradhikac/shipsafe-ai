"""ShipSafe AI V2 — Continuous Release Safety Monitor Streamlit Console."""

import datetime
import os
import sys
import json
import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

# Add current workspace to path
sys.path.insert(0, os.path.abspath("."))

from shipsafe.database import (
    SessionLocal,
    init_db,
    Repository,
    WebhookEvent,
    AnalysisRun,
    AgentRun,
    Finding,
    RequirementCheck,
    RemediationAction,
)
from worker.worker import AnalysisWorker
import asyncio

# Page Configuration
st.set_page_config(
    page_title="ShipSafe AI — Continuous Release Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Enterprise CSS (Light/Graphite theme, compact badges, clean tables)
st.markdown("""
<style>
    /* Global typography and layout */
    .stApp {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #0f172a;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #0f172a;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    /* Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    /* Status Badges */
    .badge-ready {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 700;
        border: 1px solid #bbf7d0;
        display: inline-block;
    }
    .badge-attention {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 700;
        border: 1px solid #fef08a;
        display: inline-block;
    }
    .badge-blocked {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 700;
        border: 1px solid #fecaca;
        display: inline-block;
    }
    .badge-pending {
        background-color: #e2e8f0;
        color: #475569;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid #cbd5e1;
        display: inline-block;
    }

    /* Severity badges */
    .sev-critical { color: #dc2626; font-weight: 700; }
    .sev-high { color: #ea580c; font-weight: 600; }
    .sev-medium { color: #d97706; font-weight: 600; }
    .sev-low { color: #2563eb; font-weight: 500; }
    .sev-info { color: #64748b; font-weight: 500; }

    /* Card Panels */
    .repo-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)


def get_db_session():
    init_db()
    return SessionLocal()


def render_status_badge(status_str: str) -> str:
    s = (status_str or "PENDING").upper()
    if s == "READY":
        return f'<span class="badge-ready">✓ RELEASE READY</span>'
    elif s == "ATTENTION":
        return f'<span class="badge-attention">⚠ ATTENTION REQUIRED</span>'
    elif s == "BLOCKED":
        return f'<span class="badge-blocked">🛑 RELEASE BLOCKED</span>'
    else:
        return f'<span class="badge-pending">⏳ {s}</span>'


# Sidebar Navigation
st.sidebar.markdown("### 🛡️ **ShipSafe AI**")
st.sidebar.markdown("*Continuous Release Safety Monitor*")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    [
        "1. Overview",
        "2. Repositories",
        "3. Live Events",
        "4. Release Runs",
        "5. Findings",
        "6. Impact Map",
        "7. Requirements",
        "8. Release Simulation",
        "9. Remediation",
        "10. Settings",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Runtime AI**: Grok-4.7")
st.sidebar.markdown(f"**Env**: `{os.environ.get('APP_ENV', 'development')}`")

db = get_db_session()

# ==========================================
# 1. OVERVIEW
# ==========================================
if menu == "1. Overview":
    st.title("Continuous Release Safety Monitor")
    st.markdown("Real-time automated release risk monitoring across arbitrary repositories.")

    repos = db.query(Repository).filter(Repository.is_active == True).all()
    total_runs = db.query(AnalysisRun).count()
    blocked_runs = db.query(AnalysisRun).filter(AnalysisRun.release_status == "BLOCKED").count()
    ready_runs = db.query(AnalysisRun).filter(AnalysisRun.release_status == "READY").count()

    # High-level Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monitored Repositories", len(repos))
    m2.metric("Total Analysis Runs", total_runs)
    m3.metric("Blocked Releases", blocked_runs)
    m4.metric("Certified Ready", ready_runs)

    st.markdown("---")
    st.subheader("Monitored Repository Status")

    if not repos:
        st.info("No repositories currently monitored. Navigate to '2. Repositories' to register a repository.")
    else:
        for r in repos:
            latest_run = db.query(AnalysisRun).filter(
                AnalysisRun.repository_id == r.id
            ).order_by(AnalysisRun.id.desc()).first()

            status_html = render_status_badge(latest_run.release_status if latest_run else "PENDING")
            open_findings = len(latest_run.findings) if latest_run else 0
            last_event = latest_run.event_type if latest_run else "None"
            last_analyzed = latest_run.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if (latest_run and latest_run.completed_at) else "Never"

            is_example = "carehub" in r.name.lower() or (r.local_path and "carehub" in r.local_path.lower())
            repo_display_name = f"{r.name} *(Example Repository)*" if is_example else r.name

            col_card, col_action = st.columns([4, 1])
            with col_card:
                st.markdown(f"""
                <div class="repo-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0; font-size:1.1rem;">📦 {repo_display_name}</h4>
                        {status_html}
                    </div>
                    <div style="color:#64748b; font-size:0.88rem; margin-top:8px;">
                        Branch: <code>{r.default_branch}</code> &nbsp;|&nbsp;
                        Last Event: <strong>{last_event}</strong> &nbsp;|&nbsp;
                        Last Analyzed: <strong>{last_analyzed}</strong> &nbsp;|&nbsp;
                        Findings: <strong>{open_findings}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_action:
                st.write("")
                if st.button(f"Analyze Now", key=f"run_btn_{r.id}"):
                    # Enqueue manual run and trigger worker
                    new_run = AnalysisRun(
                        repository_id=r.id,
                        event_type="manual",
                        branch=r.default_branch,
                        status="PENDING",
                        release_status="PENDING",
                        summary={"trigger": "streamlit_ui"}
                    )
                    db.add(new_run)
                    db.commit()
                    db.refresh(new_run)
                    worker = AnalysisWorker()
                    asyncio.run(worker.process_job_by_id(new_run.id))
                    st.rerun()

# ==========================================
# 2. REPOSITORIES
# ==========================================
elif menu == "2. Repositories":
    st.title("Repository Management")
    st.markdown("Register and configure software repositories for event-driven continuous monitoring.")

    # Registration Form
    with st.expander("➕ Register New Repository", expanded=False):
        with st.form("new_repo_form"):
            repo_name = st.text_input("Repository Name (e.g. billing-service)")
            repo_url = st.text_input("Repository URL (e.g. https://github.com/myorg/billing-service.git)")
            local_path = st.text_input("Local File Path (Optional, for local testing)")
            branch = st.text_input("Monitored Branch", value="main")
            submitted = st.form_submit_button("Register Repository")
            if submitted and repo_name and repo_url:
                new_repo = Repository(
                    name=repo_name,
                    repo_url=repo_url,
                    local_path=local_path or None,
                    default_branch=branch,
                    is_active=True
                )
                db.add(new_repo)
                db.commit()
                st.success(f"Registered repository '{repo_name}' successfully!")
                st.rerun()

    # List registered repositories
    repos = db.query(Repository).all()
    if repos:
        repo_data = []
        for r in repos:
            is_example = "carehub" in r.name.lower() or (r.local_path and "carehub" in r.local_path.lower())
            repo_data.append({
                "ID": r.id,
                "Name": f"{r.name} (Example)" if is_example else r.name,
                "URL": r.repo_url,
                "Local Path": r.local_path or "—",
                "Branch": r.default_branch,
                "Active": "✓ Active" if r.is_active else "Inactive",
                "Created At": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—"
            })
        st.dataframe(pd.DataFrame(repo_data), use_container_width=True)
    else:
        st.info("No repositories registered.")

# ==========================================
# 3. LIVE EVENTS
# ==========================================
elif menu == "3. Live Events":
    st.title("Live GitHub Webhook Events")
    st.markdown("Cryptographically verified, deduplicated webhook event stream from GitHub.")

    events = db.query(WebhookEvent).order_by(WebhookEvent.id.desc()).limit(50).all()
    if events:
        event_rows = []
        for e in events:
            # find linked run
            linked_run = db.query(AnalysisRun).filter(AnalysisRun.webhook_event_id == e.id).first()
            event_rows.append({
                "ID": e.id,
                "Delivery UUID": e.delivery_id,
                "Event Type": e.event_type,
                "Received At": e.received_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "Linked Run ID": f"#{linked_run.id}" if linked_run else "None",
                "Run Status": linked_run.status if linked_run else "—",
                "Gate Result": linked_run.release_status if linked_run else "—",
            })
        st.dataframe(pd.DataFrame(event_rows), use_container_width=True)

        st.subheader("Event Payload Inspector")
        event_select = st.selectbox(
            "Select Webhook Event ID to inspect payload",
            [e.id for e in events],
            format_func=lambda x: f"Event #{x} ({next(e.event_type for e in events if e.id == x)})"
        )
        selected_event = next(e for e in events if e.id == event_select)
        st.json(selected_event.payload)
    else:
        st.info("No webhook events received yet. Use `scripts/simulate_webhook.py` to send test events.")

# ==========================================
# 4. RELEASE RUNS
# ==========================================
elif menu == "4. Release Runs":
    st.title("Release Analysis Runs")
    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.info("No analysis runs recorded.")
    else:
        run_options = {r.id: f"Run #{r.id} - {r.repository.name if r.repository else 'Repo'} [{r.event_type}] ({r.release_status})" for r in runs}
        selected_run_id = st.selectbox("Select Release Run", list(run_options.keys()), format_func=lambda x: run_options[x])
        selected_run = db.query(AnalysisRun).filter(AnalysisRun.id == selected_run_id).first()

        # Run Header Summary
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Repository:** {selected_run.repository.name if selected_run.repository else '—'}")
        c2.markdown(f"**Branch / Event:** `{selected_run.branch}` ({selected_run.event_type})")
        c3.markdown(f"**Duration:** {selected_run.duration_seconds}s")
        c4.markdown(f"**Gate Status:** {render_status_badge(selected_run.release_status)}", unsafe_allow_html=True)

        st.markdown("---")
        # Sub-metrics
        summary = selected_run.summary or {}
        test_summary = summary.get("test_summary", {})
        sev_counts = summary.get("severity_counts", {})

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tests Passed", f"{test_summary.get('passed', 0)} / {test_summary.get('total', 0)}")
        s2.metric("Critical Security", sev_counts.get("CRITICAL", 0))
        s3.metric("High Concerns", sev_counts.get("HIGH", 0))
        s4.metric("Verified Findings", summary.get("verified_findings_count", len(selected_run.findings)))

        # Agent Runs Breakdown
        st.subheader("Specialist Grok Agent Executions")
        agent_runs = db.query(AgentRun).filter(AgentRun.analysis_run_id == selected_run.id).all()
        if agent_runs:
            ar_data = [
                {
                    "Agent Name": ar.agent_name.replace("_", " ").title(),
                    "Status": ar.status,
                    "Duration": f"{ar.duration_seconds}s",
                    "Findings Generated": len(ar.raw_output.get("findings", [])),
                }
                for ar in agent_runs
            ]
            st.table(pd.DataFrame(ar_data))

# ==========================================
# 5. FINDINGS
# ==========================================
elif menu == "5. Findings":
    st.title("Verified Release Findings")
    st.markdown("Grounded findings backed by concrete repository evidence (file presence, line bounds, and diff traces).")

    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()
    if not runs:
        st.info("No runs available.")
    else:
        run_id = st.selectbox("Filter by Run ID", [r.id for r in runs], format_func=lambda x: f"Run #{x} ({next(r.release_status for r in runs if r.id == x)})")
        
        severity_filter = st.multiselect(
            "Filter Severity",
            ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
            default=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        )

        query = db.query(Finding).filter(Finding.analysis_run_id == run_id)
        if severity_filter:
            query = query.filter(Finding.severity.in_(severity_filter))
        findings = query.order_by(Finding.id.asc()).all()

        if findings:
            for f in findings:
                sev_color = {
                    "CRITICAL": "sev-critical",
                    "HIGH": "sev-high",
                    "MEDIUM": "sev-medium",
                    "LOW": "sev-low",
                }.get(f.severity, "sev-info")

                verified_badge = "✅ Grounded in Repo" if f.verified else "⚠️ Unverified Line"
                with st.expander(f"[{f.severity}] {f.finding_id}: {f.title} — {f.file}:{f.line_start or 1}"):
                    st.markdown(f"**Agent:** `{f.agent_name}` &nbsp;|&nbsp; **Verification:** *{verified_badge}* ({f.verification_notes})")
                    st.markdown(f"**Description:** {f.description}")
                    st.markdown(f"**Affected Components:** {', '.join(f.affected_components or [])}")
                    if f.evidence:
                        st.code(f.evidence, language="python")
                    st.markdown(f"**Recommendation:** {f.recommendation}")
        else:
            st.success("No findings matching the selected filters.")

# ==========================================
# 6. IMPACT MAP
# ==========================================
elif menu == "6. Impact Map":
    st.title("Blast Radius & Impact Map")
    st.markdown("Visual mapping connecting commits → changed files → components → APIs → tests.")

    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()
    if runs:
        run_id = st.selectbox("Select Run for Impact Mapping", [r.id for r in runs])
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        summary = run.summary or {}
        sim = summary.get("simulation", {})
        nodes = sim.get("blast_radius_nodes", [])

        if nodes:
            st.subheader(f"Affected Components for Run #{run.id}")
            df_nodes = pd.DataFrame(nodes)
            st.dataframe(df_nodes, use_container_width=True)

            st.markdown("### Blast Radius Topology Flow")
            st.markdown(f"""
```mermaid
graph TD
    Commit["Commit: {run.head_sha[:8] if run.head_sha else 'HEAD'}"] --> Files["Changed Files"]
    Files --> Comp["Affected Components ({len(nodes)})"]
    Comp --> API["API Contracts & Routes"]
    Comp --> DB["Database & Models"]
    API --> Workflows["User Workflows"]
    DB --> Workflows
    Workflows --> Tests["Regression Test Suite"]
```
            """)
        else:
            st.info("No blast radius nodes recorded for this run.")

# ==========================================
# 7. REQUIREMENTS
# ==========================================
elif menu == "7. Requirements":
    st.title("Requirement Traceability Matrix")
    st.markdown("Traceability connecting requirements (R001–R005) directly to implementation evidence and test status.")

    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()
    if runs:
        run_id = st.selectbox("Select Analysis Run", [r.id for r in runs])
        req_checks = db.query(RequirementCheck).filter(RequirementCheck.analysis_run_id == run_id).all()
        if req_checks:
            req_data = [
                {
                    "Requirement ID": rc.requirement_id,
                    "Title": rc.title,
                    "Status": "✅ COMPLIANT" if rc.status == "COMPLIANT" else "❌ NON_COMPLIANT",
                    "Evidence": rc.evidence,
                    "Related Finding Count": len(rc.related_findings or [])
                }
                for rc in req_checks
            ]
            st.dataframe(pd.DataFrame(req_data), use_container_width=True)
        else:
            st.info("No requirement checks recorded for this run.")

# ==========================================
# 8. RELEASE SIMULATION
# ==========================================
elif menu == "8. Release Simulation":
    st.title("Release Impact Simulation")
    st.markdown("Deterministic blast radius modeling and regression failure simulation.")

    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()
    if runs:
        run_id = st.selectbox("Select Run to Simulate", [r.id for r in runs])
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        sim = (run.summary or {}).get("simulation", {})

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Highest Risk Component:** `{sim.get('highest_risk_component', 'None')}`")
            st.markdown("**Test Gaps:**")
            for tg in sim.get("test_gaps", []):
                st.markdown(f"- ⚠️ {tg}")
        with c2:
            st.markdown("**API Concerns:**")
            for ac in sim.get("api_concerns", []):
                st.markdown(f"- 🔍 {ac}")
            st.markdown("**Database Concerns:**")
            for dc in sim.get("database_concerns", []):
                st.markdown(f"- 🗄️ {dc}")

        st.subheader("Recommended Pre-Deployment Validations")
        for rec in sim.get("recommended_validations", []):
            st.markdown(f"- 🛡️ {rec}")

# ==========================================
# 9. REMEDIATION
# ==========================================
elif menu == "9. Remediation":
    st.title("Verified Remediation & Recheck")
    st.markdown("Generate safe, verified patches for confirmed blockers and recheck release readiness.")

    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()
    if runs:
        run_id = st.selectbox("Select Run to Remediate", [r.id for r in runs])
        actions = db.query(RemediationAction).filter(RemediationAction.analysis_run_id == run_id).all()

        col_act1, col_act2 = st.columns([3, 1])
        with col_act2:
            if st.button("Generate Fix Proposals"):
                # Propose remediations for verified findings
                findings = db.query(Finding).filter(
                    Finding.analysis_run_id == run_id,
                    Finding.verified == True
                ).all()
                for f in findings:
                    diff_patch = (
                        f"--- a/{f.file}\n"
                        f"+++ b/{f.file}\n"
                        f"@@ -{f.line_start or 1},1 +{f.line_start or 1},1 @@\n"
                        f"# Automated Patch for {f.finding_id}: {f.title}\n"
                        f"# {f.recommendation}\n"
                    )
                    act = RemediationAction(
                        analysis_run_id=run_id,
                        title=f"Fix {f.finding_id}: {f.title}",
                        description=f.recommendation or f.description,
                        target_file=f.file,
                        patch_diff=diff_patch,
                        status="PROPOSED"
                    )
                    db.add(act)
                db.commit()
                st.success("Remediation proposals generated!")
                st.rerun()

        if actions:
            for a in actions:
                with st.expander(f"Patch Proposal: {a.title} ({a.status})", expanded=True):
                    st.markdown(f"**Target File:** `{a.target_file}`")
                    st.markdown(f"**Description:** {a.description}")
                    st.code(a.patch_diff, language="diff")

                    if a.status == "PROPOSED":
                        if st.button(f"[ APPLY PATCH ]", key=f"apply_{a.id}"):
                            a.status = "APPLIED"
                            a.applied_at = datetime.datetime.utcnow()
                            db.commit()
                            st.success(f"Patch applied! Rechecking release candidate...")
                            # Trigger recheck run
                            recheck_run = AnalysisRun(
                                repository_id=runs[0].repository_id,
                                event_type="recheck",
                                branch=runs[0].branch,
                                status="PENDING",
                                release_status="PENDING",
                                summary={"remediation_action_id": a.id}
                            )
                            db.add(recheck_run)
                            db.commit()
                            db.refresh(recheck_run)
                            worker = AnalysisWorker()
                            asyncio.run(worker.process_job_by_id(recheck_run.id))
                            st.rerun()
                    else:
                        st.info(f"Applied on {a.applied_at.strftime('%Y-%m-%d %H:%M:%S UTC') if a.applied_at else 'Earlier'}")
        else:
            st.info("No proposed patches yet. Click 'Generate Fix Proposals'.")

# ==========================================
# 10. SETTINGS
# ==========================================
elif menu == "10. Settings":
    st.title("System Settings & Configuration")
    
    st.subheader("AI Provider Settings")
    st.markdown(f"**Provider:** `{os.environ.get('AI_PROVIDER', 'grok')}`")
    st.markdown(f"**Model:** `{os.environ.get('XAI_MODEL', 'grok-4.7')}`")
    has_api_key = bool(os.environ.get("XAI_API_KEY"))
    st.markdown(f"**xAI API Key Configured:** `{'Yes (Masked)' if has_api_key else 'No (Using deterministic fallback)'}`")

    st.subheader("Database Connection")
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./shipsafe.db")
    masked_db = db_url.split("@")[-1] if "@" in db_url else db_url
    st.markdown(f"**Active Database:** `{masked_db}`")

    st.subheader("Security & Webhooks")
    has_secret = bool(os.environ.get("GITHUB_WEBHOOK_SECRET"))
    st.markdown(f"**GitHub Webhook Secret Configured:** `{'Yes (HMAC-SHA256 Active)' if has_secret else 'No (Development Mode)'}`")

db.close()
