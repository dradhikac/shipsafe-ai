"""ShipSafe Git change analyzer.

Reads the real Git repository state using the ``git`` executable via
subprocess.  Does NOT invent or hard-code changed files.

All Git calls use explicit argument lists, capture stdout/stderr, and check
return codes.  ``shell=True`` is never used.
"""

from __future__ import annotations

import subprocess
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileChange:
    """A single file-level change as reported by Git."""
    status: str          # M, A, D, R, C, U, ?, etc.
    path: str
    old_path: Optional[str] = None   # populated for renames/copies


@dataclass
class DiffSummary:
    """Aggregate diff statistics for the working tree vs HEAD."""
    lines_added: int = 0
    lines_deleted: int = 0
    files_changed: int = 0


@dataclass
class GitState:
    """Complete snapshot of the current repository state."""
    repo_root: str
    branch: str
    head_commit: str
    head_message: str
    changed_files: list[FileChange] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    diff_summary: DiffSummary = field(default_factory=DiffSummary)
    is_clean: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _find_repo_root(start: Optional[str] = None) -> str:
    """Walk up the directory tree to find the Git repository root.

    Raises RuntimeError if no Git repository is found.
    """
    search = Path(start).resolve() if start else Path.cwd().resolve()
    for candidate in [search, *search.parents]:
        if (candidate / ".git").exists():
            return str(candidate)
    raise RuntimeError(
        f"No Git repository found starting from: {search}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_repo_root(start: Optional[str] = None) -> str:
    """Return the absolute path to the repository root.

    Uses ``git rev-parse --show-toplevel`` first; falls back to walking the
    directory tree so tests can use temporary directories that may not have a
    full Git initialisation.
    """
    search = str(Path(start).resolve()) if start else str(Path.cwd().resolve())
    rc, stdout, _ = _run(["git", "rev-parse", "--show-toplevel"], cwd=search)
    if rc == 0 and stdout.strip():
        return stdout.strip()
    # Fallback: walk upward looking for .git
    return _find_repo_root(search)


def get_branch(repo_root: str) -> str:
    """Return the current branch name, or a detached-HEAD description."""
    rc, stdout, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if rc == 0:
        return stdout.strip()
    # Detached HEAD or other state
    rc2, stdout2, _ = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root)
    if rc2 == 0:
        return f"(detached HEAD {stdout2.strip()})"
    return "unknown"


def get_head_commit(repo_root: str) -> tuple[str, str]:
    """Return (full_sha, first_line_of_message) for HEAD."""
    rc, stdout, _ = _run(
        ["git", "log", "-1", "--format=%H%n%s"],
        cwd=repo_root,
    )
    if rc != 0 or not stdout.strip():
        return ("unknown", "")
    lines = stdout.strip().splitlines()
    sha = lines[0] if lines else "unknown"
    msg = lines[1] if len(lines) > 1 else ""
    return sha, msg


def get_changed_files(repo_root: str) -> list[FileChange]:
    """Return all changed files in the working tree (staged + unstaged).

    Uses ``git status --porcelain=v1`` which produces a stable,
    machine-readable format.

    Format:
        XY PATH
        XY ORIG_PATH -> PATH   (renames)

    X = index status, Y = working-tree status
    """
    rc, stdout, stderr = _run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
    )
    if rc != 0:
        raise RuntimeError(f"git status failed: {stderr.strip()}")

    changes: list[FileChange] = []
    for line in stdout.splitlines():
        if not line:
            continue
        xy = line[:2]
        rest = line[3:]

        # Renames: "R  old -> new" or "R  old\0new" depending on version
        if " -> " in rest:
            parts = rest.split(" -> ", 1)
            old_path = parts[0].strip().strip('"')
            new_path = parts[1].strip().strip('"')
            changes.append(FileChange(status=xy.strip() or "R",
                                      path=new_path,
                                      old_path=old_path))
        else:
            path = rest.strip().strip('"')
            status = xy.strip()
            changes.append(FileChange(status=status, path=path))

    return changes


def get_untracked_files(changed_files: list[FileChange]) -> list[str]:
    """Extract untracked file paths from a list of FileChange objects."""
    return [c.path for c in changed_files if c.status == "??"]


def get_diff_summary(repo_root: str) -> DiffSummary:
    """Return aggregate diff statistics for all tracked changes vs HEAD.

    Uses ``git diff --stat HEAD`` to cover both staged and unstaged changes.
    Falls back to zero counts if the repository is clean or has no commits.
    """
    rc, stdout, _ = _run(
        ["git", "diff", "--stat", "HEAD"],
        cwd=repo_root,
    )
    if rc != 0 or not stdout.strip():
        return DiffSummary()

    added = deleted = files_changed = 0
    for line in stdout.splitlines():
        line = line.strip()
        # "N file(s) changed, X insertion(s)(+), Y deletion(s)(-)"
        if "changed" in line:
            import re
            fc = re.search(r"(\d+) file", line)
            ia = re.search(r"(\d+) insertion", line)
            id_ = re.search(r"(\d+) deletion", line)
            if fc:
                files_changed = int(fc.group(1))
            if ia:
                added = int(ia.group(1))
            if id_:
                deleted = int(id_.group(1))

    return DiffSummary(
        lines_added=added,
        lines_deleted=deleted,
        files_changed=files_changed,
    )


def analyze(start: Optional[str] = None) -> GitState:
    """Run a full Git analysis and return a :class:`GitState`.

    ``start`` may be a directory inside the repository; the root will be
    located automatically.

    Returns a :class:`GitState` with ``error`` set (rather than raising) if
    Git is unavailable or the directory is not a repository.
    """
    try:
        repo_root = get_repo_root(start)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        return GitState(
            repo_root=str(start or Path.cwd()),
            branch="unknown",
            head_commit="unknown",
            head_message="",
            error=str(exc),
        )

    try:
        branch = get_branch(repo_root)
        head_commit, head_message = get_head_commit(repo_root)
        changed = get_changed_files(repo_root)
        untracked = get_untracked_files(changed)
        diff_summary = get_diff_summary(repo_root)
        is_clean = len([c for c in changed if c.status != "??"]) == 0

        return GitState(
            repo_root=repo_root,
            branch=branch,
            head_commit=head_commit,
            head_message=head_message,
            changed_files=changed,
            untracked_files=untracked,
            diff_summary=diff_summary,
            is_clean=is_clean,
        )
    except Exception as exc:  # noqa: BLE001
        return GitState(
            repo_root=repo_root,
            branch="unknown",
            head_commit="unknown",
            head_message="",
            error=str(exc),
        )


def to_dict(state: GitState) -> dict:
    """Serialise a :class:`GitState` to a JSON-compatible dict."""
    return {
        "repo_root": state.repo_root,
        "branch": state.branch,
        "head_commit": state.head_commit,
        "head_message": state.head_message,
        "is_clean": state.is_clean,
        "error": state.error,
        "changed_files": [
            {
                "status": c.status,
                "path": c.path,
                "old_path": c.old_path,
            }
            for c in state.changed_files
        ],
        "untracked_files": state.untracked_files,
        "diff_summary": {
            "files_changed": state.diff_summary.files_changed,
            "lines_added": state.diff_summary.lines_added,
            "lines_deleted": state.diff_summary.lines_deleted,
        },
    }
