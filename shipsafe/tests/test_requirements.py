"""Tests for shipsafe.analyzer.requirements.

Verifies:
- all five requirements load from the canonical Markdown file
- duplicate IDs raise RequirementsError
- missing required IDs raise RequirementsError
- empty requirement text raises RequirementsError
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from shipsafe.analyzer import requirements as req_module
from shipsafe.analyzer.requirements import (
    Requirement,
    RequirementsError,
    REQUIRED_IDS,
    load,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    """Return the repository root by walking up from this file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return str(parent)
    pytest.skip("Repository root not found")


def _write_requirements(tmp_path: Path, content: str) -> str:
    req_dir = tmp_path / "requirements"
    req_dir.mkdir()
    req_file = req_dir / "CareHub_v2_4_Requirements.md"
    req_file.write_text(content, encoding="utf-8")
    return str(req_file)


# ---------------------------------------------------------------------------
# Loading from the real requirements file
# ---------------------------------------------------------------------------

def test_load_returns_list_of_requirement_objects():
    root = _repo_root()
    reqs = load(repo_root=root)
    assert isinstance(reqs, list)
    assert len(reqs) > 0
    for r in reqs:
        assert isinstance(r, Requirement)


def test_load_all_five_requirements():
    root = _repo_root()
    reqs = load(repo_root=root)
    ids = {r.requirement_id for r in reqs}
    for req_id in REQUIRED_IDS:
        assert req_id in ids, f"Missing requirement: {req_id}"


def test_all_requirements_have_non_empty_text():
    root = _repo_root()
    reqs = load(repo_root=root)
    for r in reqs:
        assert r.requirement_text.strip(), (
            f"Requirement {r.requirement_id} has empty text"
        )


def test_all_requirements_have_source_file():
    root = _repo_root()
    reqs = load(repo_root=root)
    for r in reqs:
        assert r.source_file, f"Requirement {r.requirement_id} missing source_file"


def test_requirement_ids_match_expected_pattern():
    root = _repo_root()
    reqs = load(repo_root=root)
    import re
    for r in reqs:
        assert re.match(r"^R\d{3}$", r.requirement_id), (
            f"Unexpected requirement ID format: {r.requirement_id}"
        )


# ---------------------------------------------------------------------------
# Validation: duplicate IDs
# ---------------------------------------------------------------------------

def test_duplicate_id_raises_requirements_error(tmp_path):
    content = """
## R001

Text for R001.

## R001

Duplicate.

## R002

Text for R002.

## R003

Text for R003.

## R004

Text for R004.

## R005

Text for R005.
"""
    req_file = _write_requirements(tmp_path, content)
    with pytest.raises(RequirementsError, match="Duplicate"):
        load(requirements_file=req_file)


# ---------------------------------------------------------------------------
# Validation: missing required ID
# ---------------------------------------------------------------------------

def test_missing_required_id_raises_requirements_error(tmp_path):
    # Only provide R001-R004, missing R005
    content = """
## R001

Text for R001.

## R002

Text for R002.

## R003

Text for R003.

## R004

Text for R004.
"""
    req_file = _write_requirements(tmp_path, content)
    with pytest.raises(RequirementsError, match="R005"):
        load(requirements_file=req_file)


# ---------------------------------------------------------------------------
# Validation: empty text
# ---------------------------------------------------------------------------

def test_empty_requirement_text_raises_requirements_error(tmp_path):
    # R001 heading present but no body
    content = """
## R001

## R002

Text for R002.

## R003

Text for R003.

## R004

Text for R004.

## R005

Text for R005.
"""
    req_file = _write_requirements(tmp_path, content)
    with pytest.raises(RequirementsError, match="empty text"):
        load(requirements_file=req_file)


# ---------------------------------------------------------------------------
# File not found
# ---------------------------------------------------------------------------

def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(requirements_file=str(tmp_path / "nonexistent.md"))


# ---------------------------------------------------------------------------
# to_dict serialisation
# ---------------------------------------------------------------------------

def test_to_dict_returns_list_of_dicts():
    root = _repo_root()
    reqs = load(repo_root=root)
    result = req_module.to_dict(reqs)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, dict)
        assert "requirement_id" in item
        assert "requirement_text" in item
        assert "source_file" in item


def test_to_dict_is_json_serialisable():
    root = _repo_root()
    reqs = load(repo_root=root)
    import json
    serialised = json.dumps(req_module.to_dict(reqs))
    assert isinstance(serialised, str)
