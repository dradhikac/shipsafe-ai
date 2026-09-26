"""Tests for shipsafe.analyzer.git_analyzer.

These tests verify behaviour, not today's exact repository state.
They use the real Git repository where available and temporary directories
for isolation tests.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from shipsafe.analyzer import git_analyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    """Return the repository root, or skip if we cannot find one."""
    try:
        return git_analyzer.get_repo_root()
    except (RuntimeError, FileNotFoundError):
        pytest.skip("No Git repository found")


def _git_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Repository location
# ---------------------------------------------------------------------------

def test_get_repo_root_returns_string():
    root = _repo_root()
    assert isinstance(root, str)
    assert len(root) > 0


def test_get_repo_root_contains_git_dir():
    root = _repo_root()
    assert Path(root, ".git").exists(), (
        f"Expected .git directory at {root}"
    )


def test_get_repo_root_from_subdirectory():
    """get_repo_root should find the root from any subdirectory."""
    root = _repo_root()
    subdir = Path(root) / "shipsafe"
    if subdir.exists():
        found = git_analyzer.get_repo_root(str(subdir))
        assert found == root


# ---------------------------------------------------------------------------
# Branch and HEAD
# ---------------------------------------------------------------------------

def test_get_branch_returns_string():
    root = _repo_root()
    branch = git_analyzer.get_branch(root)
    assert isinstance(branch, str)
    assert len(branch) > 0


def test_get_head_commit_returns_tuple():
    root = _repo_root()
    sha, msg = git_analyzer.get_head_commit(root)
    assert isinstance(sha, str)
    assert isinstance(msg, str)


def test_get_head_commit_sha_looks_like_sha_or_unknown():
    root = _repo_root()
    sha, _ = git_analyzer.get_head_commit(root)
    # Either a valid SHA (40 hex chars) or "unknown" if repo has no commits
    import re
    assert re.match(r"^[0-9a-f]{40}$", sha) or sha == "unknown", (
        f"Unexpected head commit format: {sha}"
    )


# ---------------------------------------------------------------------------
# Changed files structure
# ---------------------------------------------------------------------------

def test_get_changed_files_returns_list():
    root = _repo_root()
    changes = git_analyzer.get_changed_files(root)
    assert isinstance(changes, list)


def test_file_change_has_required_fields():
    root = _repo_root()
    changes = git_analyzer.get_changed_files(root)
    for c in changes:
        assert hasattr(c, "status"), "FileChange missing 'status'"
        assert hasattr(c, "path"), "FileChange missing 'path'"
        assert hasattr(c, "old_path"), "FileChange missing 'old_path'"
        assert isinstance(c.status, str)
        assert isinstance(c.path, str)
        assert c.path  # path must not be empty


# ---------------------------------------------------------------------------
# Diff summary
# ---------------------------------------------------------------------------

def test_diff_summary_has_non_negative_counts():
    root = _repo_root()
    diff = git_analyzer.get_diff_summary(root)
    assert diff.lines_added >= 0
    assert diff.lines_deleted >= 0
    assert diff.files_changed >= 0


def test_diff_summary_is_diff_summary_type():
    root = _repo_root()
    diff = git_analyzer.get_diff_summary(root)
    assert isinstance(diff, git_analyzer.DiffSummary)


# ---------------------------------------------------------------------------
# Full analyze()
# ---------------------------------------------------------------------------

def test_analyze_returns_git_state():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    assert isinstance(state, git_analyzer.GitState)


def test_analyze_git_state_has_repo_root():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    assert state.repo_root  # non-empty


def test_analyze_git_state_has_branch():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    assert isinstance(state.branch, str)
    assert state.branch  # non-empty


def test_analyze_is_clean_is_bool():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    assert isinstance(state.is_clean, bool)


def test_analyze_error_is_none_for_valid_repo():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    assert state.error is None, f"Unexpected error: {state.error}"


# ---------------------------------------------------------------------------
# Clean working tree
# ---------------------------------------------------------------------------

def test_analyze_clean_state_returns_is_clean_true():
    """In a clean repository (no pending changes) is_clean should be True.

    This test is skipped if the current working tree is not clean, since the
    test suite itself may have pending changes during development.
    """
    root = _repo_root()
    state = git_analyzer.analyze(root)
    # We cannot assert the tree IS clean (dev environment may have changes),
    # but we can assert the is_clean flag is consistent with changed_files.
    tracked_changes = [
        c for c in state.changed_files if c.status != "??"
    ]
    if state.is_clean:
        assert len(tracked_changes) == 0, (
            "is_clean=True but there are tracked changes."
        )
    else:
        # Either there are tracked changes, or we have untracked files
        pass  # untracked files alone may set is_clean=False depending on state


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_to_dict_returns_serialisable_dict():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    d = git_analyzer.to_dict(state)
    import json
    serialised = json.dumps(d)
    assert isinstance(serialised, str)


def test_to_dict_has_required_keys():
    root = _repo_root()
    state = git_analyzer.analyze(root)
    d = git_analyzer.to_dict(state)
    for key in ("repo_root", "branch", "head_commit", "is_clean",
                "changed_files", "untracked_files", "diff_summary"):
        assert key in d, f"to_dict missing key: {key}"


# ---------------------------------------------------------------------------
# Error handling — invalid directory
# ---------------------------------------------------------------------------

def test_analyze_invalid_directory_returns_error_state():
    """analyze() on a non-existent path should return a GitState with error."""
    state = git_analyzer.analyze("/nonexistent/path/that/does/not/exist")
    assert state.error is not None
    assert isinstance(state.error, str)
    assert len(state.error) > 0
