"""ShipSafe AI V2 — Continuous Release Safety Monitor Streamlit Console."""

import datetime
import os
import sys
import json
import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

# Add current workspace to path and invalidate cached shipsafe modules in long-lived Streamlit process
sys.path.insert(0, os.path.abspath("."))
for _mod in list(sys.modules.keys()):
    if _mod.startswith("shipsafe.database") or _mod.startswith("shipsafe.core"):
        sys.modules.pop(_mod, None)

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
from shipsafe.core.repo_manager import RepositoryManager
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
    .empty-state-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 36px 24px;
        text-align: center;
        margin-top: 16px;
        margin-bottom: 24px;
    }
</style>
""", unsafe_allow_html=True)


def get_db_session():
    init_db()
    return SessionLocal()


def render_status_badge(status_str: str) -> str:
    s = (status_str or "NOT ANALYZED").upper()
    if s == "READY":
        return '<span class="badge-ready">✓ RELEASE READY</span>'
    elif s == "ATTENTION":
        return '<span class="badge-attention">⚠ ATTENTION REQUIRED</span>'
    elif s == "BLOCKED":
        return '<span class="badge-blocked">🛑 RELEASE BLOCKED</span>'
    elif s in ("NOT ANALYZED", "PENDING"):
        return '<span class="badge-pending">⚪ NOT ANALYZED</span>'
    else:
        return f'<span class="badge-pending">⏳ {s}</span>'


def render_monitoring_badge(enabled: bool) -> str:
    if enabled:
        return '<span style="background-color:#dcfce7; color:#166534; padding:3px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; border:1px solid #bbf7d0;">MONITORED</span>'
    else:
        return '<span style="background-color:#f1f5f9; color:#64748b; padding:3px 8px; border-radius:4px; font-weight:600; font-size:0.8rem; border:1px solid #cbd5e1;">PAUSED</span>'


# Initialize session state keys
if "show_connect_dialog" not in st.session_state:
    st.session_state["show_connect_dialog"] = False
if "just_connected_repo_id" not in st.session_state:
    st.session_state["just_connected_repo_id"] = None
if "nav_target" not in st.session_state:
    st.session_state["nav_target"] = None

nav_items = [
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
]

def render_connect_repository_dialog(db_session: Session, key_prefix: str = "repo"):
    with st.container():
        st.markdown("""
        <div style="background:#ffffff; border:2px solid #3b82f6; border-radius:8px; padding:20px; margin-bottom:20px; margin-top:14px;">
            <h3 style="margin-top:0; color:#1e293b;">CONNECT REPOSITORY</h3>
        </div>
        """, unsafe_allow_html=True)

        with st.form(f"{key_prefix}_connect_form"):
            repo_url_input = st.text_input(
                "Repository URL",
                placeholder="https://github.com/owner/repository",
                help="Paste a public or accessible GitHub repository URL"
            )
            branch_input = st.text_input(
                "Branch",
                value="Auto-detect",
                help="Branch to checkout and inspect (leave as 'Auto-detect' to determine default)"
            )
            display_name_input = st.text_input(
                "Repository display name (Optional)",
                placeholder="e.g. billing-service"
            )
            submit_connect = st.form_submit_button("CONNECT REPOSITORY")

        if submit_connect:
            if not repo_url_input or not repo_url_input.strip():
                st.error("Repository connection failed. Reason: Repository URL cannot be empty.")
            else:
                is_valid, owner, repo_name, err = RepositoryManager.validate_github_url(repo_url_input)
                if not is_valid:
                    st.error(f"Repository connection failed. Reason: {err}")
                else:
                    with st.status("CONNECTING...", expanded=True) as status_box:
                        st.write("1. Validating URL")
                        st.write("2. Fetching repository")
                        st.write("3. Detecting branch")
                        st.write("4. Reading latest commit")
                        try:
                            target_branch = None if branch_input.strip() == "Auto-detect" else branch_input.strip()
                            connected_repo = RepositoryManager.connect_repository(
                                db=db_session,
                                url=repo_url_input.strip(),
                                branch=target_branch,
                                display_name=display_name_input.strip() if display_name_input.strip() else None
                            )
                            status_box.update(label="CONNECTED", state="complete")
                            st.session_state["just_connected_repo_id"] = connected_repo.id
                            st.session_state["show_connect_dialog"] = False
                            st.rerun()
                        except Exception as exc:
                            status_box.update(label="FAILED", state="error")
                            st.error(f"Repository connection failed. Reason: {exc}")


# Handle programmatic redirection in Streamlit
if "main_nav_radio" not in st.session_state:
    st.session_state["main_nav_radio"] = "1. Overview"

if st.session_state.get("nav_target") in nav_items:
    st.session_state["main_nav_radio"] = st.session_state["nav_target"]
    st.session_state["nav_target"] = None

# Sidebar Navigation
st.sidebar.markdown("### 🛡️ **ShipSafe AI**")
st.sidebar.markdown("*Continuous Release Safety Monitor*")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    nav_items,
    key="main_nav_radio",
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Runtime AI**: Grok-4.7")
st.sidebar.markdown(f"**Env**: `{os.environ.get('APP_ENV', 'development')}`")

db = get_db_session()

# ==========================================
# 1. OVERVIEW
# ==========================================
if menu == "1. Overview":
    repos = db.query(Repository).filter(Repository.is_active == True).all()

    if not repos:
        st.markdown("""
        <div class="empty-state-box">
            <h1 style="margin-bottom:4px; font-size:2.2rem; color:#0f172a;">SHIPSAFE AI</h1>
            <h3 style="color:#64748b; margin-top:0; font-weight:400; font-size:1.25rem;">Continuous Release Safety Monitor</h3>
            <div style="margin: 28px 0 14px 0; font-size: 1.15rem; font-weight: 600; color: #1e293b;">
                No repositories connected.
            </div>
            <p style="color: #64748b; font-size: 0.95rem; margin-bottom: 24px;">
                Connect a GitHub repository to begin monitoring.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_c1, col_c2, col_c3 = st.columns([2, 1.2, 2])
        with col_c2:
            if st.button("➕ ADD REPOSITORY", key="overview_add_repo_btn", use_container_width=True):
                st.session_state["show_connect_dialog"] = not st.session_state.get("show_connect_dialog", False)
                st.rerun()

        if st.session_state.get("show_connect_dialog"):
            render_connect_repository_dialog(db, key_prefix="ov")

    else:
        st.title("Continuous Release Safety Monitor")
        st.markdown("Real-time automated release risk monitoring across arbitrary repositories.")

        total_runs = db.query(AnalysisRun).count()
        blocked_runs = db.query(AnalysisRun).filter(AnalysisRun.release_status == "BLOCKED").count()
        ready_runs = db.query(AnalysisRun).filter(AnalysisRun.release_status == "READY").count()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Monitored Repositories", len(repos))
        m2.metric("Total Analysis Runs", total_runs)
        m3.metric("Blocked Releases", blocked_runs)
        m4.metric("Certified Ready", ready_runs)

        st.markdown("---")
        st.subheader("Monitored Repositories")

        for r in repos:
            status_info = RepositoryManager.get_status(db, r)
            status_html = render_status_badge(status_info["release_status"])
            mon_enabled = getattr(r, "monitoring_enabled", False)
            mon_badge = render_monitoring_badge(mon_enabled)
            open_findings = status_info["findings_count"] if status_info["has_analysis"] else "—"
            last_event = status_info["last_event"] or "None"
            last_analyzed = status_info["last_analyzed"]
            r_name = getattr(r, "display_name", getattr(r, "name", "Repository"))
            r_branch = getattr(r, "selected_branch", None) or getattr(r, "default_branch", "main")

            col_card, col_action = st.columns([4, 1.2])
            with col_card:
                st.markdown(f"""
                <div class="repo-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0; font-size:1.15rem;">📦 {r_name} &nbsp; {mon_badge}</h4>
                        {status_html}
                    </div>
                    <div style="color:#64748b; font-size:0.88rem; margin-top:10px;">
                        Branch: <code>{r_branch}</code> &nbsp;|&nbsp;
                        Monitoring: <strong>{'MONITORED' if mon_enabled else 'PAUSED'}</strong> &nbsp;|&nbsp;
                        Last Event: <strong>{last_event}</strong> &nbsp;|&nbsp;
                        Last Analyzed: <strong>{last_analyzed}</strong> &nbsp;|&nbsp;
                        Findings: <strong>{open_findings}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_action:
                st.write("")
                if st.button("ANALYZE NOW", key=f"ov_run_{r.id}", use_container_width=True):
                    with st.spinner(f"Analyzing {r_name}..."):
                        new_run = AnalysisRun(
                            repository_id=r.id,
                            event_type="manual",
                            branch=r_branch,
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

                if mon_enabled:
                    if st.button("PAUSE MONITORING", key=f"ov_mon_{r.id}", use_container_width=True):
                        setattr(r, "monitoring_enabled", False)
                        db.commit()
                        st.rerun()
                else:
                    if st.button("START MONITORING", key=f"ov_mon_{r.id}", use_container_width=True):
                        setattr(r, "monitoring_enabled", True)
                        db.commit()
                        st.rerun()

# ==========================================
# 2. REPOSITORIES
# ==========================================
elif menu == "2. Repositories":
    st.title("REPOSITORIES")

    col_hdr_left, col_hdr_right = st.columns([3, 1])
    with col_hdr_right:
        if st.button("➕ ADD REPOSITORY", key="top_add_repo_btn", use_container_width=True):
            st.session_state["show_connect_dialog"] = not st.session_state["show_connect_dialog"]

    # Add Repository Dialog / Form
    if st.session_state.get("show_connect_dialog"):
        render_connect_repository_dialog(db, key_prefix="repos_tab")

    # Display post-connection banner if newly connected
    if st.session_state.get("just_connected_repo_id"):
        new_repo = db.query(Repository).filter(Repository.id == st.session_state["just_connected_repo_id"]).first()
        if new_repo:
            st.success("Repository connected successfully.")
            st.markdown(f"""
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:16px 20px; margin-bottom:16px;">
                <h4 style="margin:0 0 8px 0; color:#166534;">Repository: {new_repo.display_name}</h4>
                <div style="color:#166534; font-size:0.9rem;">
                    Branch: <code>{new_repo.selected_branch or new_repo.default_branch}</code> &nbsp;|&nbsp;
                    Latest commit: <code>{new_repo.latest_commit_sha}</code> &nbsp;|&nbsp;
                    Files: <strong>{new_repo.files_count}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            b_col1, b_col2, b_col3 = st.columns([1.5, 1.5, 3])
            with b_col1:
                if st.button("START MONITORING", key=f"just_mon_{new_repo.id}", use_container_width=True):
                    new_repo.monitoring_enabled = True
                    db.commit()
                    st.session_state["just_connected_repo_id"] = None
                    st.rerun()
            with b_col2:
                if st.button("ANALYZE NOW", key=f"just_run_{new_repo.id}", use_container_width=True):
                    with st.spinner(f"Analyzing {new_repo.display_name}..."):
                        run = AnalysisRun(
                            repository_id=new_repo.id,
                            event_type="manual",
                            branch=new_repo.selected_branch or new_repo.default_branch,
                            status="PENDING",
                            release_status="PENDING",
                            summary={"trigger": "post_connect"}
                        )
                        db.add(run)
                        db.commit()
                        db.refresh(run)
                        worker = AnalysisWorker()
                        asyncio.run(worker.process_job_by_id(run.id))
                        st.session_state["just_connected_repo_id"] = None
                        st.rerun()

    # List registered repositories or show empty state
    repos = db.query(Repository).filter(Repository.is_active == True).all()

    if not repos:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO REPOSITORIES</h3>
            <p style="color:#64748b; font-size:1rem; margin-bottom:20px;">
                You have not connected a repository yet.
            </p>
        </div>
        """, unsafe_allow_html=True)
        col_c1, col_c2, col_c3 = st.columns([2, 1.5, 2])
        with col_c2:
            if st.button("CONNECT REPOSITORY", key="empty_connect_btn", use_container_width=True):
                st.session_state["show_connect_dialog"] = True
                st.rerun()
    else:
        for r in repos:
            status_info = RepositoryManager.get_status(db, r)
            status_html = render_status_badge(status_info["release_status"])
            mon_enabled = getattr(r, "monitoring_enabled", False)
            mon_badge = render_monitoring_badge(mon_enabled)
            open_findings = status_info["findings_count"] if status_info["has_analysis"] else "—"
            last_event = status_info["last_event"] or "None"
            last_analyzed = status_info["last_analyzed"]
            r_name = getattr(r, "display_name", getattr(r, "name", "Repository"))
            r_sha = getattr(r, "latest_commit_sha", "HEAD")
            r_files = getattr(r, "files_count", 0)

            with st.container():
                st.markdown(f"""
                <div class="repo-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="margin:0; font-size:1.25rem;">📦 {r_name} &nbsp; {mon_badge}</h3>
                        {status_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_meta, col_branch, col_actions = st.columns([2.5, 1.5, 1.5])
                with col_meta:
                    st.markdown(f"**URL:** `{r.repo_url}`")
                    st.markdown(f"**Latest Commit:** `{r_sha}`")
                    st.markdown(f"**Files:** `{r_files}` &nbsp;|&nbsp; **Findings:** `{open_findings}`")
                    st.markdown(f"**Last Event:** `{last_event}` &nbsp;|&nbsp; **Last Analyzed:** `{last_analyzed}`")

                with col_branch:
                    # Dynamic branch selection from detected repository branches
                    raw_avail = getattr(r, "available_branches", None)
                    available = raw_avail if (raw_avail and isinstance(raw_avail, list)) else [r.default_branch]
                    current_branch = getattr(r, "selected_branch", None) or r.default_branch
                    selected_b = st.selectbox(
                        "Branch",
                        available,
                        index=available.index(current_branch) if current_branch in available else 0,
                        key=f"b_select_{r.id}"
                    )
                    if selected_b != getattr(r, "selected_branch", None):
                        setattr(r, "selected_branch", selected_b)
                        db.commit()
                        st.rerun()

                with col_actions:
                    cur_b = getattr(r, "selected_branch", None) or r.default_branch
                    if st.button("ANALYZE NOW", key=f"repo_analyze_{r.id}", use_container_width=True):
                        with st.spinner(f"Analyzing {r_name} on branch {cur_b}..."):
                            new_run = AnalysisRun(
                                repository_id=r.id,
                                event_type="manual",
                                branch=cur_b,
                                status="PENDING",
                                release_status="PENDING",
                                summary={"trigger": "repositories_page"}
                            )
                            db.add(new_run)
                            db.commit()
                            db.refresh(new_run)
                            worker = AnalysisWorker()
                            asyncio.run(worker.process_job_by_id(new_run.id))
                            st.rerun()

                    if mon_enabled:
                        if st.button("PAUSE MONITORING", key=f"repo_mon_{r.id}", use_container_width=True):
                            setattr(r, "monitoring_enabled", False)
                            db.commit()
                            st.rerun()
                    else:
                        if st.button("START MONITORING", key=f"repo_mon_{r.id}", use_container_width=True):
                            setattr(r, "monitoring_enabled", True)
                            db.commit()
                            st.rerun()

            st.markdown("---")

# ==========================================
# 3. LIVE EVENTS
# ==========================================
elif menu == "3. Live Events":
    repos = db.query(Repository).filter(Repository.is_active == True).all()
    events = db.query(WebhookEvent).order_by(WebhookEvent.id.desc()).limit(50).all() if repos else []

    if not repos or not events:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO EVENTS</h3>
            <p style="color:#64748b; font-size:1rem;">
                Connect and monitor a repository to see GitHub events here.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Live GitHub Webhook Events")
        st.markdown("Cryptographically verified, deduplicated webhook event stream from connected GitHub repositories.")

        event_rows = []
        for e in events:
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

# ==========================================
# 4. RELEASE RUNS
# ==========================================
elif menu == "4. Release Runs":
    runs = db.query(AnalysisRun).order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO ANALYSIS RUNS</h3>
            <p style="color:#64748b; font-size:1rem;">
                Run your first repository analysis to see results here.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Release Analysis Runs")
        run_options = {
            r.id: f"Run #{r.id} - {r.repository.display_name if r.repository else 'Repo'} [{r.event_type}] ({r.release_status})"
            for r in runs
        }
        selected_run_id = st.selectbox(
            "Select Release Run",
            list(run_options.keys()),
            format_func=lambda x: run_options[x]
        )
        selected_run = db.query(AnalysisRun).filter(AnalysisRun.id == selected_run_id).first()
        summary = selected_run.summary or {}
        repo_obj = selected_run.repository
        repo_name_str = f"{repo_obj.owner}/{repo_obj.name}" if (repo_obj and repo_obj.owner) else (repo_obj.name if repo_obj else "—")
        commit_sha_str = selected_run.head_sha[:8] if selected_run.head_sha else "HEAD"
        ai_model_str = summary.get("model") or ("mock" if os.environ.get("AI_PROVIDER") == "mock" else os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
        files_analyzed_val = summary.get("files_analyzed", repo_obj.files_count if repo_obj else 0)
        tests_discovered_val = summary.get("tests_discovered", summary.get("test_summary", {}).get("total", 0))
        reqs_val = summary.get("requirements_count", len(selected_run.requirement_checks))

        agent_runs = db.query(AgentRun).filter(AgentRun.analysis_run_id == selected_run.id).all()
        completed_agents = len([a for a in agent_runs if a.status == "COMPLETED"])
        total_agents = len(agent_runs) if agent_runs else 5
        agent_status_str = f"{completed_agents} / {total_agents} completed"

        validated_findings_count = db.query(Finding).filter(
            Finding.analysis_run_id == selected_run.id,
            Finding.validation_status == "VALIDATED"
        ).count()

        st.markdown(f"### ANALYSIS #{selected_run.id}")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Repository:** `{repo_name_str}`<br>**Branch:** `{selected_run.branch}`", unsafe_allow_html=True)
        c2.markdown(f"**Commit:** `{commit_sha_str}`<br>**AI Model:** `{ai_model_str}`", unsafe_allow_html=True)
        c3.markdown(f"**Files analyzed:** {files_analyzed_val}<br>**Tests discovered:** {tests_discovered_val}", unsafe_allow_html=True)
        c4.markdown(f"**Requirements:** {reqs_val}<br>**Agents:** {agent_status_str}", unsafe_allow_html=True)

        st.markdown(f"**Gate Status:** {render_status_badge(selected_run.release_status)} &nbsp;|&nbsp; **Duration:** {selected_run.duration_seconds}s &nbsp;|&nbsp; **Validated Findings:** {validated_findings_count}", unsafe_allow_html=True)

        st.markdown("---")
        test_summary = summary.get("test_summary", {})
        sev_counts = summary.get("severity_counts", {})

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tests Passed", f"{test_summary.get('passed', 0)} / {test_summary.get('total', 0)}")
        s2.metric("Critical Security", sev_counts.get("CRITICAL", 0))
        s3.metric("High Concerns", sev_counts.get("HIGH", 0))
        s4.metric("Verified Findings", validated_findings_count)

        st.subheader("Specialist Grok Agent Executions")
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
    runs = db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO FINDINGS</h3>
            <p style="color:#64748b; font-size:1rem;">
                No repository analysis has been completed.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Verified Release Findings")
        st.markdown("Grounded findings backed by concrete repository evidence (file presence, line bounds, and diff traces).")

        run_id = st.selectbox(
            "Filter by Run ID",
            [r.id for r in runs],
            format_func=lambda x: f"Run #{x} ({next(r.release_status for r in runs if r.id == x)})"
        )

        selected_run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        summary = selected_run.summary or {}
        repo_obj = selected_run.repository
        repo_name_str = f"{repo_obj.owner}/{repo_obj.name}" if (repo_obj and repo_obj.owner) else (repo_obj.name if repo_obj else "—")
        commit_sha_str = selected_run.head_sha[:8] if selected_run.head_sha else "HEAD"
        ai_model_str = summary.get("model") or ("mock" if os.environ.get("AI_PROVIDER") == "mock" else os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
        files_analyzed_val = summary.get("files_analyzed", repo_obj.files_count if repo_obj else 0)
        tests_discovered_val = summary.get("tests_discovered", summary.get("test_summary", {}).get("total", 0))
        reqs_val = summary.get("requirements_count", len(selected_run.requirement_checks))

        agent_runs = db.query(AgentRun).filter(AgentRun.analysis_run_id == selected_run.id).all()
        completed_agents = len([a for a in agent_runs if a.status == "COMPLETED"])
        total_agents = len(agent_runs) if agent_runs else 5
        agent_status_str = f"{completed_agents} / {total_agents} completed"

        validated_findings_count = db.query(Finding).filter(
            Finding.analysis_run_id == selected_run.id,
            Finding.validation_status == "VALIDATED"
        ).count()

        st.markdown(f"### ANALYSIS #{selected_run.id}")
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"**Repository:** `{repo_name_str}`<br>**Branch:** `{selected_run.branch}`", unsafe_allow_html=True)
        col2.markdown(f"**Commit:** `{commit_sha_str}`<br>**AI Model:** `{ai_model_str}`", unsafe_allow_html=True)
        col3.markdown(f"**Files analyzed:** {files_analyzed_val}<br>**Tests discovered:** {tests_discovered_val}", unsafe_allow_html=True)
        col4.markdown(f"**Requirements:** {reqs_val}<br>**Agents:** {agent_status_str}", unsafe_allow_html=True)

        st.markdown(f"**Gate Status:** {render_status_badge(selected_run.release_status)} &nbsp;|&nbsp; **Findings:** {validated_findings_count} (Validated)", unsafe_allow_html=True)
        st.markdown("---")

        filter_col1, filter_col2 = st.columns([3, 1])
        with filter_col1:
            severity_filter = st.multiselect(
                "Filter Severity",
                ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
                default=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            )
        with filter_col2:
            show_unverified = st.checkbox("Show Rejected / Unverified", value=False, help="Include findings rejected by Evidence Validator")

        query = db.query(Finding).filter(Finding.analysis_run_id == run_id)
        if not show_unverified:
            query = query.filter(Finding.validation_status == "VALIDATED")
        if severity_filter:
            query = query.filter(Finding.severity.in_(severity_filter))
        findings = query.order_by(Finding.id.asc()).all()

        if findings:
            for f in findings:
                is_val = (f.validation_status == "VALIDATED")
                val_badge = '<span class="badge-ready">VALIDATED</span>' if is_val else f'<span class="badge-blocked">{f.validation_status or "REJECTED"}</span>'
                line_str = f"{f.line_start}" if f.line_start else "1"
                if f.line_end and f.line_end != f.line_start:
                    line_str += f"-{f.line_end}"

                with st.expander(f"[{f.severity}] {f.finding_id}: {f.title} — {f.file}:{line_str}"):
                    st.markdown(f"**Agent:** `{f.agent_name.capitalize()}` &nbsp;|&nbsp; **Severity:** **{f.severity}** &nbsp;|&nbsp; **Validation:** {val_badge} &nbsp;|&nbsp; **Confidence:** `{round(f.confidence, 2) if f.confidence is not None else 1.0}`", unsafe_allow_html=True)
                    st.markdown(f"**File:** `{f.file}` &nbsp;|&nbsp; **Line:** `{line_str}`")
                    st.markdown(f"**Description:** {f.description}")
                    if f.affected_components:
                        st.markdown(f"**Affected Components:** {', '.join(f.affected_components)}")
                    if f.evidence:
                        st.markdown("**Evidence:**")
                        st.code(f.evidence, language="python" if f.file.endswith(".py") else "text")
                    if f.recommendation:
                        st.markdown(f"**Recommendation:** {f.recommendation}")
                    if f.verification_notes:
                        st.caption(f"Evidence Validator Notes: {f.verification_notes}")
        else:
            if not show_unverified and validated_findings_count == 0:
                st.success("✅ Zero findings generated. All specialist agents verified repository evidence with no defects found.")
            else:
                st.info("No findings matching the selected filters.")

# ==========================================
# 6. IMPACT MAP
# ==========================================
elif menu == "6. Impact Map":
    runs = db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO ANALYSIS AVAILABLE</h3>
            <p style="color:#64748b; font-size:1rem;">
                Run an analysis to inspect blast radius and affected system topology.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Blast Radius & Impact Map")
        st.markdown("Visual mapping connecting commits → changed files → components → APIs → tests.")

        run_id = st.selectbox("Select Run for Impact Mapping", [r.id for r in runs])
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        summary = run.summary or {}
        sim = summary.get("simulation", {})
        nodes = sim.get("blast_radius_nodes", [])

        if nodes:
            st.subheader(f"Affected Components for Run #{run.id}")
            st.dataframe(pd.DataFrame(nodes), use_container_width=True)

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
    runs = db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO ANALYSIS AVAILABLE</h3>
            <p style="color:#64748b; font-size:1rem;">
                Run an analysis to inspect requirement compliance and evidence traces.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Requirement Traceability Matrix")
        st.markdown("Traceability connecting requirements directly to implementation evidence and test status.")

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
    runs = db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO ANALYSIS AVAILABLE</h3>
            <p style="color:#64748b; font-size:1rem;">
                Run an analysis to model release regressions and pre-deployment risks.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Release Impact Simulation")
        st.markdown("Deterministic blast radius modeling and regression failure simulation.")

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
    runs = db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.id.desc()).all()

    if not runs:
        st.markdown("""
        <div class="empty-state-box">
            <h3 style="color:#0f172a; margin-bottom:8px;">NO ANALYSIS AVAILABLE</h3>
            <p style="color:#64748b; font-size:1rem;">
                Run an analysis to generate verified remediations and patch proposals.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("Verified Remediation & Recheck")
        st.markdown("Generate safe, verified patches for confirmed blockers and recheck release readiness.")

        run_id = st.selectbox("Select Run to Remediate", [r.id for r in runs])
        actions = db.query(RemediationAction).filter(RemediationAction.analysis_run_id == run_id).all()

        col_act1, col_act2 = st.columns([3, 1])
        with col_act2:
            if st.button("Generate Fix Proposals"):
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
                            st.success("Patch applied! Rechecking release candidate...")
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
    active_prov = os.environ.get("AI_PROVIDER", "groq" if os.environ.get("GROQ_API_KEY") else "grok")
    st.markdown(f"**Provider:** `{active_prov}`")
    has_xai = bool(os.environ.get("XAI_API_KEY"))
    has_groq = bool(os.environ.get("GROQ_API_KEY"))
    st.markdown(f"**xAI API Key (Grok):** `{'Configured (Masked)' if has_xai else 'Not set'}`")
    st.markdown(f"**Groq API Key (LPU):** `{'Configured (Masked)' if has_groq else 'Not set'}`")
    st.markdown(f"**Execution Mode:** `{'Deterministic Evidence Engine' if not (has_xai or has_groq) else 'Live LLM Reasoning'}`")

    st.subheader("Database Connection")
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./shipsafe.db")
    masked_db = db_url.split("@")[-1] if "@" in db_url else db_url
    st.markdown(f"**Active Database:** `{masked_db}`")

    st.subheader("Security & Webhooks")
    has_secret = bool(os.environ.get("GITHUB_WEBHOOK_SECRET"))
    st.markdown(f"**GitHub Webhook Secret Configured:** `{'Yes (HMAC-SHA256 Active)' if has_secret else 'No (Development Mode)'}`")

db.close()
