"""Repository abstraction for arbitrary local or remote codebases."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from .git import GitController
from .discovery import ProjectDiscovery
from .secrets import SecretFilter


class Repository:
    """Represents a code repository under analysis."""

    def __init__(self, root_dir: str, name: Optional[str] = None, url: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.name = name or os.path.basename(self.root_dir)
        self.url = url
        self.git = GitController(self.root_dir)
        self.discovery = ProjectDiscovery(self.root_dir)

    def exists(self) -> bool:
        return os.path.isdir(self.root_dir)

    def file_exists(self, relative_path: str) -> bool:
        """Verify if a relative file path exists in the repository."""
        full_path = os.path.join(self.root_dir, relative_path)
        return os.path.isfile(full_path)

    def read_file(self, relative_path: str, max_chars: int = 50000) -> Optional[str]:
        """Read text content of a repository file, applying secret redaction."""
        if SecretFilter.is_blocked_path(relative_path):
            return None

        full_path = os.path.join(self.root_dir, relative_path)
        if not os.path.isfile(full_path):
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return SecretFilter.redact_text(content)
        except Exception:
            return None

    def read_snippet(self, relative_path: str, line_start: int, line_end: int) -> Optional[str]:
        """Read a specific line range from a file (1-indexed, inclusive)."""
        content = self.read_file(relative_path)
        if content is None:
            return None

        lines = content.splitlines()
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)

        if start_idx >= len(lines):
            return None

        return "\n".join(lines[start_idx:end_idx])

    def verify_line(self, relative_path: str, line: Optional[int]) -> bool:
        """Verify that the given line number exists within the file."""
        if line is None or line < 1:
            return False
        content = self.read_file(relative_path)
        if content is None:
            return False
        return line <= len(content.splitlines())

    def get_metadata(self) -> Dict[str, Any]:
        """Get repository metadata and git commit information."""
        meta = {
            "name": self.name,
            "root_dir": self.root_dir,
            "url": self.url,
            "is_git": self.git.is_git_repo(),
            "head_sha": None,
            "branch": None,
            "commit_author": None,
            "commit_message": None,
        }
        if meta["is_git"]:
            try:
                meta["head_sha"] = self.git.get_head_sha()
                meta["branch"] = self.git.get_current_branch()
                meta["commit_author"] = self.git.get_commit_author()
                meta["commit_message"] = self.git.get_commit_message()
            except Exception:
                pass
        return meta
