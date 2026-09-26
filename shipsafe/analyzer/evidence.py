"""ShipSafe evidence module.

Evidence is the foundation of all findings in ShipSafe AI.

An :class:`Evidence` record must be traceable to real repository state or
real command execution.  Generic or inferred evidence must be flagged
explicitly; only evidence with concrete sources may support CONFIRMED findings.

Evidence types
--------------
CODE
    A specific code pattern in a file at a known location.
TEST_FAILURE
    A named test that failed, with its output.
COMMAND_OUTPUT
    The stdout/stderr of a real command execution.
FILE_PRESENCE
    The presence or absence of a specific file.
GIT_CHANGE
    A file or hunk identified in the Git diff.
REQUIREMENT_GAP
    A gap between a requirement and the implementation, with file evidence.
SCHEMA_CHANGE
    A model or schema change with database evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Valid evidence types
# ---------------------------------------------------------------------------

EVIDENCE_TYPES = frozenset({
    "CODE",
    "TEST_FAILURE",
    "COMMAND_OUTPUT",
    "FILE_PRESENCE",
    "GIT_CHANGE",
    "REQUIREMENT_GAP",
    "SCHEMA_CHANGE",
})


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """A single piece of traceable evidence.

    Not every field must be populated.  ``evidence_type`` and at least one
    locating field (``file_path``, ``command``, or ``test_name``) should be
    set to make the evidence actionable.
    """

    evidence_type: str
    description: str

    # Source location
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    symbol: Optional[str] = None          # function or class name

    # Linkage
    requirement_id: Optional[str] = None  # e.g. "R001"
    test_name: Optional[str] = None

    # Command execution
    command: Optional[list[str]] = None
    output: Optional[str] = None          # stdout/stderr excerpt

    # Validation flag
    is_concrete: bool = True  # False = inferred/unconfirmed


class EvidenceError(ValueError):
    """Raised when an evidence record fails validation."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build(
    evidence_type: str,
    description: str,
    *,
    file_path: Optional[str] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    symbol: Optional[str] = None,
    requirement_id: Optional[str] = None,
    test_name: Optional[str] = None,
    command: Optional[list[str]] = None,
    output: Optional[str] = None,
    is_concrete: bool = True,
) -> Evidence:
    """Build and validate an :class:`Evidence` record.

    Raises :class:`EvidenceError` if the record is not valid.
    """
    if evidence_type not in EVIDENCE_TYPES:
        raise EvidenceError(
            f"Unknown evidence_type '{evidence_type}'. "
            f"Valid types: {sorted(EVIDENCE_TYPES)}"
        )
    if not description.strip():
        raise EvidenceError("Evidence description must not be empty.")

    # Concrete evidence must have at least one locating attribute
    if is_concrete and not any([file_path, command, test_name]):
        raise EvidenceError(
            "Concrete evidence must have at least one of: "
            "file_path, command, test_name. "
            "Set is_concrete=False for inferred evidence."
        )

    return Evidence(
        evidence_type=evidence_type,
        description=description,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        symbol=symbol,
        requirement_id=requirement_id,
        test_name=test_name,
        command=command,
        output=output,
        is_concrete=is_concrete,
    )


def from_git_change(file_path: str,
                    status: str,
                    description: Optional[str] = None) -> Evidence:
    """Convenience: build a GIT_CHANGE evidence item from a changed file."""
    return build(
        "GIT_CHANGE",
        description or f"File '{file_path}' has Git status '{status}'.",
        file_path=file_path,
    )


def from_command(command: list[str],
                 output: str,
                 description: str) -> Evidence:
    """Convenience: build a COMMAND_OUTPUT evidence item."""
    return build(
        "COMMAND_OUTPUT",
        description,
        command=command,
        output=output[:2000],  # truncate very long output
    )


def from_test_failure(test_name: str,
                      output: str,
                      requirement_id: Optional[str] = None) -> Evidence:
    """Convenience: build a TEST_FAILURE evidence item."""
    return build(
        "TEST_FAILURE",
        f"Test '{test_name}' failed.",
        test_name=test_name,
        output=output[:2000],
        requirement_id=requirement_id,
    )


def to_dict(ev: Evidence) -> dict:
    """Serialise an :class:`Evidence` record to a JSON-compatible dict."""
    return {
        "evidence_type": ev.evidence_type,
        "description": ev.description,
        "file_path": ev.file_path,
        "line_start": ev.line_start,
        "line_end": ev.line_end,
        "symbol": ev.symbol,
        "requirement_id": ev.requirement_id,
        "test_name": ev.test_name,
        "command": ev.command,
        "output": ev.output,
        "is_concrete": ev.is_concrete,
    }
