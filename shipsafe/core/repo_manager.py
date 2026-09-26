"""Repository Manager: handles validation, cloning, branch discovery, and metadata extraction."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.orm import Session
from shipsafe.database import SessionLocal, Repository as DBRepository, AnalysisRun
from shipsafe.core.git import GitController
from shipsafe.core.discovery import ProjectDiscovery


MANAGED_REPOS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".repos"))


class RepositoryManager:
    """Manages real Git repository connections, dynamic branch inspection, and local workspaces."""

    GITHUB_URL_REGEX = re.compile(
        r"^(?:https?://github\.com/|git@github\.com:)(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$",
        re.IGNORECASE
    )

    @classmethod
    def validate_github_url(cls, url: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Validate GitHub URL format.
        Returns: (is_valid, owner, repo_name, error_message)
        """
        if not url or not isinstance(url, str):
            return False, None, None, "Repository URL cannot be empty."

        clean_url = url.strip()
        match = cls.GITHUB_URL_REGEX.match(clean_url)
        if not match:
            return (
                False,
                None,
                None,
                "Invalid GitHub repository URL. Expected format: https://github.com/owner/repository"
            )

        owner = match.group("owner")
        repo = match.group("repo")
        return True, owner, repo, None

    @classmethod
    def connect_repository(
        cls,
        db: Session,
        url: str,
        branch: Optional[str] = None,
        display_name: Optional[str] = None,
        token: Optional[str] = None
    ) -> DBRepository:
        """
        Validate URL, clone/fetch repository, discover real branches & latest commit,
        and persist record without any seeded or fake data.
        """
        is_valid, owner, repo_name, err = cls.validate_github_url(url)
        if not is_valid:
            raise ValueError(err)

        token = token or os.environ.get("GITHUB_TOKEN")
        clean_url = f"https://github.com/{owner}/{repo_name}"

        # Target local workspace folder
        os.makedirs(MANAGED_REPOS_DIR, exist_ok=True)
        local_path = os.path.join(MANAGED_REPOS_DIR, f"{owner}_{repo_name}")

        git_ctrl = GitController(local_path)

        # Clone or fetch
        def _rm_readonly(func, p, exc):
            try:
                import stat
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass

        if os.path.isdir(local_path) and git_ctrl.is_git_repo():
            fetch_code, _, fetch_err = git_ctrl._run(["fetch", "--all", "--prune"])
            if fetch_code != 0:
                # If existing dir is corrupted, remove and re-clone
                shutil.rmtree(local_path, onerror=_rm_readonly)
                cls._clone_repo(clean_url, local_path, token)
        else:
            if os.path.exists(local_path):
                shutil.rmtree(local_path, onerror=_rm_readonly)
            cls._clone_repo(clean_url, local_path, token)

        # Discover branches dynamically from remote
        branches = cls._discover_branches(git_ctrl)
        default_branch = cls._detect_default_branch(git_ctrl, branches)

        target_branch = branch if (branch and branch != "Auto-detect" and branch in branches) else default_branch

        # Checkout selected branch and ensure working tree is populated
        git_ctrl.checkout(target_branch)
        git_ctrl._run(["reset", "--hard", "HEAD"])
        head_sha = git_ctrl.get_head_sha()

        # Count real files
        discovery = ProjectDiscovery(local_path)
        scan_info = discovery.scan()
        files_count = scan_info.get("total_files", 0)

        # Upsert in DB
        repo_record = db.query(DBRepository).filter(DBRepository.repo_url == clean_url).first()
        if not repo_record:
            repo_record = DBRepository(
                provider="github",
                owner=owner,
                name=display_name or repo_name,
                repo_url=clean_url,
                local_path=local_path,
                default_branch=default_branch,
                selected_branch=target_branch,
                available_branches=branches,
                monitoring_enabled=False,
                latest_commit_sha=head_sha,
                files_count=files_count,
                is_active=True
            )
            db.add(repo_record)
        else:
            repo_record.owner = owner
            repo_record.name = display_name or repo_record.name
            repo_record.local_path = local_path
            repo_record.default_branch = default_branch
            repo_record.selected_branch = target_branch
            repo_record.available_branches = branches
            repo_record.latest_commit_sha = head_sha
            repo_record.files_count = files_count
            repo_record.is_active = True

        db.commit()
        db.refresh(repo_record)
        return repo_record

    @classmethod
    def _clone_repo(cls, url: str, target_dir: str, token: Optional[str] = None):
        """Clone remote git repository."""
        clone_url = url
        if token:
            clone_url = url.replace("https://", f"https://x-access-token:{token}@")

        cmd = ["git", "clone", clone_url, target_dir]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            if "Authentication failed" in err_msg or "could not read Username" in err_msg:
                raise PermissionError("Authentication failed for repository. Private repositories require GITHUB_TOKEN.")
            raise RuntimeError(f"Failed to clone repository from {url}: {err_msg}")

    @classmethod
    def _discover_branches(cls, git: GitController) -> List[str]:
        """Discover actual branches present on the remote."""
        code, out, _ = git._run(["branch", "-r"])
        branches = set()
        if code == 0 and out:
            for line in out.splitlines():
                line = line.strip()
                if "->" in line:
                    continue
                if line.startswith("origin/"):
                    b_name = line.replace("origin/", "").strip()
                    if b_name:
                        branches.add(b_name)

        if not branches:
            # Fallback to local branches
            code_l, out_l, _ = git._run(["branch"])
            if code_l == 0 and out_l:
                for line in out_l.splitlines():
                    b_name = line.replace("*", "").strip()
                    if b_name:
                        branches.add(b_name)

        return sorted(list(branches)) if branches else ["main"]

    @classmethod
    def _detect_default_branch(cls, git: GitController, available_branches: List[str]) -> str:
        """Detect remote default branch (HEAD symref or common defaults)."""
        code, out, _ = git._run(["remote", "show", "origin"])
        if code == 0 and out:
            for line in out.splitlines():
                if "HEAD branch:" in line:
                    b = line.split("HEAD branch:")[1].strip()
                    if b in available_branches:
                        return b

        if "main" in available_branches:
            return "main"
        if "master" in available_branches:
            return "master"
        return available_branches[0] if available_branches else "main"

    @classmethod
    def get_status(cls, db: Session, repo: DBRepository) -> Dict[str, Any]:
        """Return real dynamic status for repository card."""
        latest_run = db.query(AnalysisRun).filter(
            AnalysisRun.repository_id == repo.id
        ).order_by(AnalysisRun.id.desc()).first()

        if not latest_run:
            return {
                "status": "NOT ANALYZED",
                "release_status": "NOT ANALYZED",
                "last_event": None,
                "last_analyzed": "Never",
                "findings_count": 0,
                "has_analysis": False,
            }

        return {
            "status": latest_run.release_status,
            "release_status": latest_run.release_status,
            "last_event": latest_run.event_type,
            "last_analyzed": latest_run.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if latest_run.completed_at else "In progress",
            "findings_count": len(latest_run.findings),
            "has_analysis": True,
        }
