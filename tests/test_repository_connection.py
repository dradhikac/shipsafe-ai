"""Comprehensive test suite for real repository connections, URL handling, and zero-seed runtime integrity."""

import os
import shutil
import pytest
from sqlalchemy.orm import Session

from shipsafe.database import (
    SessionLocal,
    init_db,
    Repository as DBRepository,
    AnalysisRun,
    Finding,
)
from shipsafe.core.repo_manager import RepositoryManager, MANAGED_REPOS_DIR
from worker.worker import AnalysisWorker
from scripts.clear_runtime_data import clear_runtime_data


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean runtime state before and after each test."""
    clear_runtime_data()
    yield
    clear_runtime_data()


def test_1_clean_database_contains_zero_repositories():
    """Test that a clean installation/reset contains exactly zero repositories."""
    init_db()
    db = SessionLocal()
    count = db.query(DBRepository).count()
    db.close()
    assert count == 0


def test_2_invalid_repository_url_rejected():
    """Test that malformed or non-GitHub URLs are rejected with descriptive errors."""
    invalid_urls = [
        "",
        "not_a_url",
        "ftp://github.com/owner/repo",
        "https://gitlab.com/owner/repo",
        "https://github.com/",
        "https://github.com/justonepart",
    ]
    for url in invalid_urls:
        is_valid, owner, repo, err = RepositoryManager.validate_github_url(url)
        assert is_valid is False
        assert err is not None


def test_3_valid_public_github_url_accepted():
    """Test that standard and .git GitHub URLs are parsed cleanly."""
    valid_urls = [
        ("https://github.com/dradhikac/shipsafe-ai", "dradhikac", "shipsafe-ai"),
        ("https://github.com/dradhikac/shipsafe-ai.git", "dradhikac", "shipsafe-ai"),
        ("https://github.com/facebook/react/", "facebook", "react"),
        ("git@github.com:octocat/Hello-World.git", "octocat", "Hello-World"),
    ]
    for url, exp_owner, exp_repo in valid_urls:
        is_valid, owner, repo, err = RepositoryManager.validate_github_url(url)
        assert is_valid is True
        assert owner.lower() == exp_owner.lower()
        assert repo.lower() == exp_repo.lower()
        assert err is None


def test_4_and_5_and_6_cloning_and_dynamic_branch_discovery():
    """Test connecting the current local git repo to verify cloning, branch discovery, and metadata."""
    init_db()
    db = SessionLocal()

    # We connect this current repository using its git remote URL
    repo_url = "https://github.com/dradhikac/shipsafe-ai"
    repo = RepositoryManager.connect_repository(
        db=db,
        url=repo_url,
        branch=None,
        display_name="ShipSafe Local Test"
    )

    # 4. Cloning works & managed workspace exists
    assert repo.local_path is not None
    assert os.path.isdir(repo.local_path)
    assert os.path.isdir(os.path.join(repo.local_path, ".git"))

    # 5. Default branch detected dynamically (not hard-coded)
    assert repo.default_branch in ("main", "master")

    # 6. Branch list detected dynamically
    assert isinstance(repo.available_branches, list)
    assert len(repo.available_branches) >= 1
    assert repo.default_branch in repo.available_branches

    # 7. Repository metadata persisted
    assert repo.latest_commit_sha is not None
    assert len(repo.latest_commit_sha) >= 7
    assert repo.files_count > 0
    assert repo.monitoring_enabled is False

    db.close()


def test_8_repository_appears_in_data_layer():
    """Test repository listing returns dynamic status without fake metrics."""
    init_db()
    db = SessionLocal()
    repo_url = "https://github.com/dradhikac/shipsafe-ai"
    repo = RepositoryManager.connect_repository(db=db, url=repo_url)

    status_info = RepositoryManager.get_status(db, repo)
    assert status_info["status"] == "NOT ANALYZED"
    assert status_info["last_event"] is None
    assert status_info["last_analyzed"] == "Never"
    assert status_info["findings_count"] == 0
    assert status_info["has_analysis"] is False
    db.close()


def test_9_analyze_now_uses_selected_repository():
    """Test that ANALYZE NOW runs deterministic evidence collection on the connected repository."""
    import asyncio
    os.environ["AI_PROVIDER"] = "mock"
    init_db()
    db = SessionLocal()

    repo_url = "https://github.com/dradhikac/shipsafe-ai"
    repo = RepositoryManager.connect_repository(db=db, url=repo_url)

    # Trigger run
    run = AnalysisRun(
        repository_id=repo.id,
        event_type="manual_test",
        branch=repo.selected_branch,
        head_sha=repo.latest_commit_sha,
        status="PENDING",
        release_status="PENDING"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    worker = AnalysisWorker()
    asyncio.run(worker.process_job_by_id(run.id))

    db.refresh(run)
    assert run.status == "COMPLETED"
    assert run.release_status in ("READY", "ATTENTION", "BLOCKED")
    assert run.duration_seconds > 0

    # Ensure status updated in repository
    status_info = RepositoryManager.get_status(db, repo)
    assert status_info["has_analysis"] is True
    assert status_info["status"] == run.release_status
    db.close()


def test_10_and_11_no_example_or_carehub_repositories_automatically():
    """Test that database initialization never auto-inserts CareHub or example rows."""
    init_db()
    db = SessionLocal()
    repos = db.query(DBRepository).all()
    repo_names = [r.name.lower() for r in repos]
    db.close()

    assert len(repos) == 0
    assert "carehub" not in repo_names
    assert "carehub-appointment-service" not in repo_names
    assert "worker-test-repo" not in repo_names
    assert "test-repo-sample" not in repo_names


def test_12_empty_state_structure():
    """Test that when 0 repos exist, no analysis runs or findings exist."""
    init_db()
    db = SessionLocal()
    assert db.query(DBRepository).count() == 0
    assert db.query(AnalysisRun).count() == 0
    assert db.query(Finding).count() == 0
    db.close()


def test_13_failed_clone_is_handled():
    """Test that cloning a non-existent remote repo raises RuntimeError cleanly."""
    init_db()
    db = SessionLocal()
    with pytest.raises(Exception) as exc_info:
        RepositoryManager.connect_repository(
            db=db,
            url="https://github.com/non-existent-user-xyz/non-existent-repo-12345"
        )
    assert "Failed to clone repository" in str(exc_info.value) or "Authentication failed" in str(exc_info.value)
    db.close()


def test_14_duplicate_repository_registration_handled_safely():
    """Test that connecting an already connected repo URL updates in-place rather than duplicating."""
    init_db()
    db = SessionLocal()
    repo_url = "https://github.com/dradhikac/shipsafe-ai"

    repo1 = RepositoryManager.connect_repository(db=db, url=repo_url, display_name="ShipSafe 1")
    id1 = repo1.id

    repo2 = RepositoryManager.connect_repository(db=db, url=repo_url, display_name="ShipSafe 2")
    id2 = repo2.id

    assert id1 == id2
    assert db.query(DBRepository).filter(DBRepository.repo_url == repo_url).count() == 1
    assert repo2.name == "ShipSafe 2"
    db.close()


def test_15_monitoring_activation_works():
    """Test toggling monitoring_enabled on a connected repository."""
    init_db()
    db = SessionLocal()
    repo_url = "https://github.com/dradhikac/shipsafe-ai"
    repo = RepositoryManager.connect_repository(db=db, url=repo_url)
    assert repo.monitoring_enabled is False

    repo.monitoring_enabled = True
    db.commit()
    db.refresh(repo)
    assert repo.monitoring_enabled is True
    db.close()


def test_16_regression_forbidden_seeded_names_not_in_runtime():
    """Regression test ensuring forbidden seeded strings are not hard-coded in runtime initialization."""
    forbidden = [
        "carehub-service",
        "carehub-appointment-service",
        "worker-test-repo",
        "test-repo-sample",
    ]

    import inspect
    from shipsafe.database import session as db_session
    from worker import worker as worker_module

    # Inspect session init_db source
    init_src = inspect.getsource(db_session.init_db)
    for name in forbidden:
        assert name not in init_src, f"Forbidden seeded name '{name}' found in init_db source!"

    # Inspect worker process_next_job source
    worker_src = inspect.getsource(worker_module.AnalysisWorker)
    for name in forbidden:
        assert name not in worker_src, f"Forbidden seeded name '{name}' found in worker source!"
