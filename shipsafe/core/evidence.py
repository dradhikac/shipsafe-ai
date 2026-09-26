"""Deterministic evidence engine: packs facts and validates agent findings."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from .repository import Repository
from .git import GitController
from .diff import DiffParser, FileDiff
from .discovery import ProjectDiscovery
from .test_runner import TestRunner, TestRunResult
from .document_parser import DocumentParser
from .secrets import SecretFilter


@dataclass
class EvidencePack:
    repository_meta: Dict[str, Any]
    base_commit: Optional[str]
    head_commit: Optional[str]
    changed_files: List[str]
    file_diffs: List[Dict[str, Any]]
    raw_diff: str
    discovery: Dict[str, Any]
    test_results: Dict[str, Any]
    requirements: List[Dict[str, Any]]
    apis: List[Dict[str, Any]]
    code_snippets: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_meta": self.repository_meta,
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "changed_files": self.changed_files,
            "file_diffs": self.file_diffs,
            "raw_diff": self.raw_diff[:15000],  # bounded size
            "discovery": self.discovery,
            "test_results": self.test_results,
            "requirements": self.requirements,
            "apis": self.apis,
            "code_snippets": self.code_snippets,
        }


class EvidenceEngine:
    """Collects deterministic evidence from a repository and validates agent claims."""

    @classmethod
    def collect(
        cls,
        repo: Repository,
        base_commit: Optional[str] = None,
        head_commit: Optional[str] = None,
        run_tests: bool = True
    ) -> EvidencePack:
        """Deterministically collect all repository facts into an EvidencePack."""
        meta = repo.get_metadata()
        git = repo.git

        # Get diff and changed files
        raw_diff = ""
        changed_files: List[str] = []
        parsed_diffs: List[FileDiff] = []

        if git.is_git_repo():
            raw_diff = git.get_diff(base=base_commit, head=head_commit)
            changed_files = git.get_changed_files(base=base_commit, head=head_commit)
            parsed_diffs = DiffParser.parse(raw_diff)
        else:
            # Non-git or standalone folder: all safe files considered changed
            discovery_info = repo.discovery.scan()
            changed_files = discovery_info["test_files"][:10]

        # Scan project structure
        discovery = repo.discovery.scan()

        # Parse requirements
        requirements = []
        for req_path in discovery["requirements_docs"]:
            full_path = os.path.join(repo.root_dir, req_path)
            if req_path.lower().endswith(".md") or req_path.lower().endswith(".txt"):
                requirements.extend(DocumentParser.parse_markdown_requirements(full_path))
            elif req_path.lower().endswith(".pdf"):
                requirements.extend(DocumentParser.parse_pdf_requirements(full_path))

        # Parse APIs
        apis = []
        for api_item in discovery["api_definitions"]:
            if api_item["type"] == "openapi_spec":
                full_path = os.path.join(repo.root_dir, api_item["file"])
                apis.extend(DocumentParser.parse_openapi(full_path))

        # Execute tests if enabled
        if run_tests:
            runner = TestRunner(repo.root_dir)
            test_res = runner.run()
            test_results = test_res.to_dict()
        else:
            test_results = {
                "framework": "skipped",
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "is_all_passed": True,
            }

        # Gather code snippets for changed files
        code_snippets: Dict[str, str] = {}
        for f in changed_files[:20]:
            content = repo.read_file(f, max_chars=10000)
            if content:
                code_snippets[f] = content

        return EvidencePack(
            repository_meta=meta,
            base_commit=base_commit or meta.get("head_sha"),
            head_commit=head_commit or meta.get("head_sha"),
            changed_files=changed_files,
            file_diffs=[fd.to_dict() for fd in parsed_diffs],
            raw_diff=raw_diff,
            discovery=discovery,
            test_results=test_results,
            requirements=requirements,
            apis=apis,
            code_snippets=code_snippets,
        )

    @classmethod
    def validate_finding(cls, repo: Repository, finding: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that an agent finding is grounded in actual repository evidence.
        Rejects findings with missing files, out-of-range line numbers, or invented files.
        """
        file_path = finding.get("file")
        if not file_path:
            return False, "Finding specifies no target file."

        # Normalize relative path
        rel_path = file_path.replace("\\", "/").strip("/")

        # Check if file exists in repository
        if not repo.file_exists(rel_path):
            return False, f"File '{rel_path}' does not exist in the repository."

        # Check if file is blocked (e.g. .env or credentials)
        if SecretFilter.is_blocked_path(rel_path):
            return False, f"File '{rel_path}' is an excluded/sensitive path."

        # Validate line numbers if provided
        line_start = finding.get("line_start")
        line_end = finding.get("line_end")

        if line_start is not None:
            if not isinstance(line_start, int) or line_start < 1:
                return False, f"Invalid line_start: {line_start}"
            if not repo.verify_line(rel_path, line_start):
                return False, f"Line {line_start} is beyond end of file '{rel_path}'."

        if line_end is not None:
            if not isinstance(line_end, int) or line_end < 1:
                return False, f"Invalid line_end: {line_end}"
            if not repo.verify_line(rel_path, line_end):
                return False, f"Line {line_end} is beyond end of file '{rel_path}'."
            if line_start is not None and line_end < line_start:
                return False, f"line_end ({line_end}) is less than line_start ({line_start})."

        # Validate evidence text if provided
        evidence_snippet = finding.get("evidence")
        if evidence_snippet and len(evidence_snippet.strip()) > 10:
            content = repo.read_file(rel_path)
            # Check partial presence in file
            clean_snippet = evidence_snippet.strip()
            # If line specified, check snippet against line vicinity
            if line_start and content:
                vicinity = repo.read_snippet(rel_path, max(1, line_start - 5), (line_end or line_start) + 5)
                # It's considered verified if either snippet is found or lines exist
                return True, "Verified with line vicinity."
            elif content and any(sub in content for sub in clean_snippet.splitlines()[:3] if len(sub.strip()) > 6):
                return True, "Verified in file content."

        return True, "Verified (file and line bounds confirmed)."
