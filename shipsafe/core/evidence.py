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
            head_commit = head_commit or meta.get("head_sha")
            raw_diff = git.get_diff(base=base_commit, head=head_commit)
            changed_files = git.get_changed_files(base=base_commit, head=head_commit)
            parsed_diffs = DiffParser.parse(raw_diff)
        else:
            discovery_info = repo.discovery.scan()
            changed_files = [f for f in discovery_info["test_files"][:10] if not f.lower().endswith("readme.md")]
            for ap in discovery_info.get("api_definitions", []):
                if ap.get("file"):
                    changed_files.append(ap.get("file"))
            for m in discovery_info.get("database", {}).get("models", []):
                changed_files.append(m)
            for sf in repo.list_files():
                if sf not in changed_files and not sf.lower().endswith(("readme.md", ".txt", ".md", ".png", ".jpg", ".svg", ".lock")):
                    changed_files.append(sf)
            changed_files = [f for f in changed_files if f][:20]

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
    def validate_finding(cls, repo: Repository, finding: Dict[str, Any], context: Optional[Any] = None) -> Tuple[bool, str]:
        """
        Validate that an agent finding is grounded in actual repository evidence.
        Delegates to EvidenceValidator.
        """
        from .evidence_validator import EvidenceValidator
        status, reason = EvidenceValidator.validate(repo, finding, context=context)
        is_valid = (status == EvidenceValidator.STATUS_VALIDATED)
        return is_valid, reason

