"""Unit tests for ShipSafe AI V2 deterministic evidence engine."""

import os
import pytest
from shipsafe.core.secrets import SecretFilter
from shipsafe.core.git import GitController
from shipsafe.core.diff import DiffParser
from shipsafe.core.discovery import ProjectDiscovery
from shipsafe.core.document_parser import DocumentParser
from shipsafe.core.repository import Repository
from shipsafe.core.evidence import EvidenceEngine
from shipsafe.core.test_runner import TestRunner, TestRunResult


def test_secret_filter_blocked_paths():
    assert SecretFilter.is_blocked_path(".env")
    assert SecretFilter.is_blocked_path(".env.production")
    assert SecretFilter.is_blocked_path("config/server.key")
    assert SecretFilter.is_blocked_path("certs/cert.pem")
    assert SecretFilter.is_blocked_path("node_modules/package/index.js")
    assert SecretFilter.is_blocked_path(".venv/bin/python")
    assert SecretFilter.is_blocked_path("app/image.png")
    assert not SecretFilter.is_blocked_path("src/index.js")
    assert not SecretFilter.is_blocked_path("routes/patients.py")


def test_secret_filter_redaction():
    text = 'API_KEY="sk_live_1234567890abcdef" bearer abcdef1234567890'
    redacted = SecretFilter.redact_text(text)
    assert "sk_live_1234567890abcdef" not in redacted
    assert "[REDACTED_SECRET]" in redacted or "[REDACTED_TOKEN]" in redacted


def test_diff_parser():
    sample_diff = """diff --git a/routes/patients.py b/routes/patients.py
index 1234567..89abcdef 100644
--- a/routes/patients.py
+++ b/routes/patients.py
@@ -10,6 +10,12 @@ def get_patients():
     return []
 
+def search_patient(query):
+    # Raw query
+    sql = f"SELECT * FROM patients WHERE name = '{query}'"
+    return sql
+
"""
    diffs = DiffParser.parse(sample_diff)
    assert len(diffs) == 1
    fd = diffs[0]
    assert fd.file_path == "routes/patients.py"
    assert fd.status == "modified"
    assert "search_patient" in fd.changed_symbols
    assert fd.additions > 0


def test_discovery_on_carehub_example():
    carehub_dir = os.path.abspath("examples/carehub")
    if os.path.isdir(carehub_dir):
        disco = ProjectDiscovery(carehub_dir)
        info = disco.scan()
        assert "python" in info["languages"]
        assert len(info["test_files"]) > 0
        assert len(info["database"]["models"]) > 0


def test_document_parser_markdown():
    req_file = os.path.abspath("requirements/CareHub_v2_4_Requirements.md")
    if os.path.exists(req_file):
        reqs = DocumentParser.parse_markdown_requirements(req_file)
        assert len(reqs) > 0
        ids = [r["id"] for r in reqs]
        assert any("R001" in i or "R002" in i for i in ids)


def test_evidence_finding_validation():
    repo = Repository(root_dir=".")
    # Valid finding: README.md exists and line 1 is within bounds
    valid_finding = {
        "file": "README.md",
        "line_start": 1,
        "line_end": 5,
        "evidence": "ShipSafe AI",
    }
    is_valid, reason = EvidenceEngine.validate_finding(repo, valid_finding)
    assert is_valid is True

    # Invalid finding: non-existent file
    invalid_file = {
        "file": "non_existent_module_xyz.py",
        "line_start": 10,
    }
    is_valid, reason = EvidenceEngine.validate_finding(repo, invalid_file)
    assert is_valid is False
    assert "does not exist" in reason

    # Invalid finding: blocked secret path
    blocked_finding = {
        "file": ".env",
        "line_start": 1,
    }
    is_valid, reason = EvidenceEngine.validate_finding(repo, blocked_finding)
    assert is_valid is False
    assert "excluded" in reason or "does not exist" in reason
