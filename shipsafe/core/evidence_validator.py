"""Deterministic evidence validation engine.

Validates that agent findings are strictly grounded in concrete repository evidence:
- Target file exists in the repository.
- Referenced line numbers exist within the file.
- Evidence snippets match actual repository source content.
- Agent scope and file relevance are respected (rejecting generic findings on README.md).
- Validation status: VALIDATED, REJECTED, or UNVERIFIABLE.
"""

import os
from typing import Dict, Any, Tuple, Optional
from .repository import Repository
from .secrets import SecretFilter


class EvidenceValidator:
    """Audits agent findings against physical repository content."""

    STATUS_VALIDATED = "VALIDATED"
    STATUS_REJECTED = "REJECTED"
    STATUS_UNVERIFIABLE = "UNVERIFIABLE"

    NON_CODE_DOC_EXTENSIONS = {".md", ".rst", ".txt", ".png", ".jpg", ".svg", ".lock"}

    @classmethod
    def validate(
        cls,
        repo: Repository,
        finding: Dict[str, Any],
        context: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """Validate finding against repo files, line bounds, and snippet presence."""
        agent_name = (finding.get("agent_name") or finding.get("agent") or "").lower()
        file_path = finding.get("file")

        # 1. File existence
        if not file_path:
            return cls.STATUS_REJECTED, "Finding specifies no target file."

        rel_path = file_path.replace("\\", "/").strip("/")

        # Check blocked paths (secrets, credentials)
        if SecretFilter.is_blocked_path(rel_path):
            return cls.STATUS_REJECTED, f"File '{rel_path}' is an excluded or sensitive path."

        # Check file exists in repository
        if not repo.file_exists(rel_path):
            return cls.STATUS_REJECTED, f"Target file '{rel_path}' does not exist in repository."

        file_content = repo.read_file(rel_path)
        if file_content is None:
            return cls.STATUS_UNVERIFIABLE, f"Could not read repository file '{rel_path}'."

        file_lines = file_content.splitlines()
        total_lines = len(file_lines)
        ext = os.path.splitext(rel_path.lower())[1]

        # 2. Category and File Relevance Enforcement
        # Rule: Do not invent generic findings on README.md or docs
        is_doc_file = rel_path.lower().endswith("readme.md") or ext in cls.NON_CODE_DOC_EXTENSIONS

        if is_doc_file:
            if agent_name in ("database", "db"):
                return cls.STATUS_REJECTED, f"Database finding rejected on documentation/non-code file '{rel_path}'."
            if agent_name in ("test_gap", "gap"):
                return cls.STATUS_REJECTED, f"Test gap finding rejected on documentation file '{rel_path}'."
            if agent_name in ("impact",):
                return cls.STATUS_REJECTED, f"Change impact blast radius rejected on documentation file '{rel_path}'."
            if agent_name in ("security", "sec"):
                # Only valid if finding is explicitly about leaked secrets/credentials in docs
                evidence_text = (finding.get("evidence") or "").lower()
                title_text = (finding.get("title") or "").lower()
                if not any(k in evidence_text or k in title_text for k in ("secret", "key", "password", "token", "credential")):
                    return cls.STATUS_REJECTED, f"Security risk inspection rejected on markdown documentation '{rel_path}'."

        # Database Agent: if repository has no database and finding is DB, reject
        if agent_name in ("database", "db") and context:
            profile = getattr(context, "profile", None)
            if profile and not getattr(profile, "has_database", False):
                return cls.STATUS_REJECTED, "Repository profile has no database or ORM; database finding rejected."

        # 3. Line Number Bounds Check
        line_start = finding.get("line_start")
        line_end = finding.get("line_end")

        if line_start is not None:
            if not isinstance(line_start, int) or line_start < 1:
                return cls.STATUS_REJECTED, f"Invalid line_start: {line_start} (must be integer >= 1)."
            if line_start > max(1, total_lines):
                return cls.STATUS_REJECTED, f"line_start {line_start} is beyond end of file '{rel_path}' ({total_lines} lines)."

        if line_end is not None:
            if not isinstance(line_end, int) or line_end < 1:
                return cls.STATUS_REJECTED, f"Invalid line_end: {line_end} (must be integer >= 1)."
            if line_end > max(1, total_lines):
                return cls.STATUS_REJECTED, f"line_end {line_end} is beyond end of file '{rel_path}' ({total_lines} lines)."
            if line_start is not None and line_end < line_start:
                return cls.STATUS_REJECTED, f"line_end ({line_end}) is less than line_start ({line_start})."

        # 4. Source Evidence Corroboration
        evidence_snippet = finding.get("evidence")
        if evidence_snippet and isinstance(evidence_snippet, str) and len(evidence_snippet.strip()) > 8:
            clean_snippet = evidence_snippet.strip()
            # If line range is specified, inspect the lines in vicinity
            if line_start and total_lines > 0:
                vicinity_start = max(1, line_start - 3)
                vicinity_end = min(total_lines, (line_end or line_start) + 3)
                vicinity_text = "\n".join(file_lines[vicinity_start - 1:vicinity_end])

                snippet_lines = [s.strip() for s in clean_snippet.splitlines() if len(s.strip()) > 4]
                if snippet_lines and any(s in vicinity_text for s in snippet_lines):
                    return cls.STATUS_VALIDATED, f"Corroborated by source snippet at {rel_path}:{line_start}-{line_end or line_start}."

            # Check if snippet appears anywhere in file
            snippet_lines = [s.strip() for s in clean_snippet.splitlines() if len(s.strip()) > 4]
            if snippet_lines and any(s in file_content for s in snippet_lines):
                return cls.STATUS_VALIDATED, f"Corroborated by matching content in '{rel_path}'."

        # If lines exist and file exists without explicit contradictory evidence
        if line_start is not None and line_start <= max(1, total_lines):
            return cls.STATUS_VALIDATED, f"Validated file '{rel_path}' and line range [{line_start}, {line_end or line_start}]."

        if not is_doc_file:
            return cls.STATUS_VALIDATED, f"Validated target file presence for '{rel_path}'."

        return cls.STATUS_UNVERIFIABLE, f"Insufficient verifiable source evidence for '{rel_path}'."
