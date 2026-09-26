"""Git controller for repository inspection, diffing, and checkout."""

import os
import subprocess
from typing import Optional, List, Tuple
from pathlib import Path


class GitController:
    """Provides safe, deterministic git operations for a target repository directory."""

    def __init__(self, repo_dir: str):
        self.repo_dir = os.path.abspath(repo_dir)

    def _run(self, args: List[str]) -> Tuple[int, str, str]:
        """Run a git command in the repository directory."""
        cmd = ["git"] + args
        proc = subprocess.run(
            cmd,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def is_git_repo(self) -> bool:
        """Check if target path is a git repository."""
        code, out, _ = self._run(["rev-parse", "--is-inside-work-tree"])
        return code == 0 and out == "true"

    def get_head_sha(self) -> str:
        """Get the full SHA of HEAD."""
        code, out, err = self._run(["rev-parse", "HEAD"])
        if code != 0:
            raise RuntimeError(f"Failed to get HEAD SHA in {self.repo_dir}: {err}")
        return out

    def get_current_branch(self) -> str:
        """Get the current branch name, or 'detached' if not on a branch."""
        code, out, _ = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        if code == 0 and out != "HEAD":
            return out
        return "detached"

    def get_diff(self, base: Optional[str] = None, head: Optional[str] = None) -> str:
        """Get git diff between base and head, or unstaged/staged diff if None."""
        args = ["diff"]
        if base and head:
            args.extend([f"{base}..{head}"])
        elif base:
            args.extend([base])
        code, out, err = self._run(args)
        if code != 0:
            # Fallback to single commit diff or empty
            return ""
        return out

    def get_changed_files(self, base: Optional[str] = None, head: Optional[str] = None) -> List[str]:
        """Get list of modified/added/deleted files."""
        args = ["diff", "--name-only"]
        if base and head:
            args.extend([f"{base}..{head}"])
        elif base:
            args.extend([base])
        code, out, _ = self._run(args)
        if code != 0 or not out:
            return []
        return [f.strip() for f in out.splitlines() if f.strip()]

    def checkout(self, commit_or_branch: str) -> bool:
        """Check out a specific commit or branch."""
        code, _, _ = self._run(["checkout", commit_or_branch])
        return code == 0

    def get_commit_message(self, commit: str = "HEAD") -> str:
        """Get commit subject and body."""
        code, out, _ = self._run(["log", "-1", "--format=%B", commit])
        return out if code == 0 else ""

    def get_commit_author(self, commit: str = "HEAD") -> str:
        """Get commit author name and email."""
        code, out, _ = self._run(["log", "-1", "--format=%an <%ae>", commit])
        return out if code == 0 else ""

    @staticmethod
    def clone(url: str, target_dir: str, token: Optional[str] = None) -> bool:
        """Clone a remote repository."""
        target_path = Path(target_dir)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        clone_url = url
        if token and "github.com" in url and "https://" in url:
            clone_url = url.replace("https://", f"https://x-access-token:{token}@")

        proc = subprocess.run(
            ["git", "clone", clone_url, str(target_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc.returncode == 0
