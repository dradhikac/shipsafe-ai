"""ShipSafe requirements loader.

Loads release requirements from the canonical Markdown source:

    requirements/CareHub_v2_4_Requirements.md

The PDF (requirements/CareHub_v2_4_Requirements.pdf) is the human-facing
document-understanding source for IBM Bob context.  This module does NOT
parse the PDF; only the Markdown file is used for deterministic loading.

Parsed requirements are returned as :class:`Requirement` dataclass instances.
The loader validates that all five IDs exist, no ID is duplicated, and that
each requirement has non-empty text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REQUIRED_IDS = ("R001", "R002", "R003", "R004", "R005")

# Match a requirement heading: "## R001" or "**R001**" at the start of a line.
_HEADING_RE = re.compile(r"^#+\s*(R\d{3})\b|^\*\*(R\d{3})\*\*", re.MULTILINE)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Requirement:
    """A single release requirement loaded from the Markdown source."""
    requirement_id: str
    requirement_text: str
    source_file: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _extract_requirements(text: str, source_file: str) -> list[Requirement]:
    """Parse requirements from Markdown text.

    Strategy:
    1. Find every requirement ID heading (## R001, **R001**, etc.).
    2. Extract all non-blank, non-heading lines that follow until the next
       requirement heading or end of file.
    3. Use the first substantive paragraph after the heading as the
       requirement text.
    """
    requirements: list[Requirement] = []
    # Split into lines for positional processing
    lines = text.splitlines()
    # Find heading positions
    heading_positions: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^#+\s*(R\d{3})\b", line) or re.match(r"^\*\*(R\d{3})\*\*", line)
        if m:
            req_id = m.group(1) or m.group(2)
            heading_positions.append((i, req_id))

    for idx, (line_no, req_id) in enumerate(heading_positions):
        # Lines belonging to this requirement: from line after heading to next heading
        if idx + 1 < len(heading_positions):
            end = heading_positions[idx + 1][0]
        else:
            end = len(lines)

        body_lines = lines[line_no + 1: end]
        # Collect non-blank, non-heading lines
        text_parts: list[str] = []
        for bl in body_lines:
            stripped = bl.strip()
            if not stripped:
                continue
            # Skip sub-headings like "Acceptance criteria:"
            if stripped.endswith(":") and len(stripped) < 50:
                continue
            # Skip markdown horizontal rules
            if re.match(r"^-{3,}$", stripped):
                continue
            text_parts.append(stripped)

        req_text = " ".join(text_parts).strip()
        requirements.append(Requirement(
            requirement_id=req_id,
            requirement_text=req_text,
            source_file=source_file,
        ))

    return requirements


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class RequirementsError(ValueError):
    """Raised when the requirements file fails validation."""


def _validate(requirements: list[Requirement]) -> None:
    """Validate the loaded requirements.

    Raises :class:`RequirementsError` with an actionable message on failure.
    """
    seen_ids: dict[str, int] = {}
    for i, req in enumerate(requirements):
        # Duplicate IDs
        if req.requirement_id in seen_ids:
            raise RequirementsError(
                f"Duplicate requirement ID '{req.requirement_id}' "
                f"found at positions {seen_ids[req.requirement_id]} and {i}."
            )
        seen_ids[req.requirement_id] = i

        # Empty text
        if not req.requirement_text.strip():
            raise RequirementsError(
                f"Requirement '{req.requirement_id}' has empty text."
            )

    # All required IDs must be present
    for required_id in REQUIRED_IDS:
        if required_id not in seen_ids:
            raise RequirementsError(
                f"Required requirement ID '{required_id}' not found in "
                f"requirements file."
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load(requirements_file: Optional[str] = None,
         repo_root: Optional[str] = None) -> list[Requirement]:
    """Load, parse, and validate requirements from the Markdown source.

    Parameters
    ----------
    requirements_file:
        Explicit path to the Markdown requirements file.  If omitted, the
        default path ``requirements/CareHub_v2_4_Requirements.md`` relative
        to ``repo_root`` (or CWD) is used.
    repo_root:
        Repository root directory.  Used only when ``requirements_file`` is
        not provided.

    Returns
    -------
    list[Requirement]
        Validated list of :class:`Requirement` instances.

    Raises
    ------
    FileNotFoundError
        If the requirements file does not exist.
    RequirementsError
        If validation fails.
    """
    if requirements_file is None:
        base = Path(repo_root) if repo_root else Path.cwd()
        requirements_file = str(base / "requirements" / "CareHub_v2_4_Requirements.md")

    path = Path(requirements_file)
    if not path.exists():
        raise FileNotFoundError(
            f"Requirements file not found: {path}\n"
            "Expected: requirements/CareHub_v2_4_Requirements.md"
        )

    text = path.read_text(encoding="utf-8")
    requirements = _extract_requirements(text, str(path))
    _validate(requirements)
    return requirements


def to_dict(requirements: list[Requirement]) -> list[dict]:
    """Serialise requirements to a JSON-compatible list of dicts."""
    return [
        {
            "requirement_id": r.requirement_id,
            "requirement_text": r.requirement_text,
            "source_file": r.source_file,
        }
        for r in requirements
    ]
