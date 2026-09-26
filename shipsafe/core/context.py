"""AnalysisContext and cache isolation for repository-grounded evaluation."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Dict, List, Any, Optional
from .discovery import RepositoryProfile


ANALYSIS_ENGINE_VERSION = "2.1.0"
PROMPT_VERSION = "2.1.0"


@dataclass
class AnalysisContext:
    """Repository-grounded analysis context uniquely bound to a repository and commit."""

    repository_id: int
    repository_url: str
    repository_name: str
    branch: str
    commit_sha: str
    base_sha: Optional[str]
    analysis_engine_version: str = ANALYSIS_ENGINE_VERSION
    prompt_version: str = PROMPT_VERSION
    profile: Optional[RepositoryProfile] = None
    changed_files: List[str] = field(default_factory=list)
    git_diff: str = ""
    repository_structure: Dict[str, Any] = field(default_factory=dict)
    test_results: Dict[str, Any] = field(default_factory=dict)
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    apis: List[Dict[str, Any]] = field(default_factory=list)
    code_snippets: Dict[str, str] = field(default_factory=dict)
    run_provenance: Dict[str, Any] = field(default_factory=dict)

    def compute_context_hash(self) -> str:
        """Deterministic SHA256 digest over the exact repository context inputs."""
        payload = {
            "repository_id": self.repository_id,
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "base_sha": self.base_sha,
            "changed_files": sorted(self.changed_files),
            "diff_sample": self.git_diff[:2000],
            "profile": self.profile.to_dict() if self.profile else {},
            "engine_version": self.analysis_engine_version,
            "prompt_version": self.prompt_version,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def compute_cache_key(self, agent_name: str) -> str:
        """Deterministic cache key strictly isolating repository, commit, engine, prompt, and agent."""
        key_source = (
            f"repo:{self.repository_id}|"
            f"url:{self.repository_url}|"
            f"commit:{self.commit_sha}|"
            f"engine:{self.analysis_engine_version}|"
            f"prompt:{self.prompt_version}|"
            f"agent:{agent_name}|"
            f"hash:{self.compute_context_hash()}"
        )
        return hashlib.sha256(key_source.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "repository_url": self.repository_url,
            "repository_name": self.repository_name,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "base_sha": self.base_sha,
            "analysis_engine_version": self.analysis_engine_version,
            "prompt_version": self.prompt_version,
            "profile": self.profile.to_dict() if self.profile else {},
            "changed_files": self.changed_files,
            "git_diff_length": len(self.git_diff),
            "repository_structure": self.repository_structure,
            "test_results": self.test_results,
            "requirements": self.requirements,
            "apis": self.apis,
            "code_snippets_keys": list(self.code_snippets.keys()),
            "context_hash": self.compute_context_hash(),
        }
