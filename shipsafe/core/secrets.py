"""Secret detection and redaction for ShipSafe AI."""

import os
import re
from pathlib import Path
from typing import List

# Paths and file patterns that must never be read, sent to LLMs, or included in evidence packs
BLOCKED_FILE_PATTERNS = [
    r"^\.env(\..+)?$",
    r".*\.pem$",
    r".*\.key$",
    r".*\.crt$",
    r".*\.pfx$",
    r".*\.p12$",
    r".*id_rsa.*",
    r".*id_ed25519.*",
    r".*credentials(\.json|\.yaml|\.xml)?$",
    r".*secrets?(\.json|\.yaml|\.xml)?$",
    r".*token.*(\.txt|\.json)?$",
]

BLOCKED_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".idea",
    ".vscode",
    "target",
    "build",
    "dist",
}

BINARY_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
}

# Regex patterns for redacting sensitive values within code snippets
REDACTION_PATTERNS = [
    # API Keys / Bearer Tokens / Generic secrets
    (re.compile(r'(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*["\']([^"\']{6,})["\']'),
     r'\1="[REDACTED_SECRET]"'),
    (re.compile(r'(?i)(bearer\s+)([A-Za-z0-9\-_\.]{12,})'),
     r'\1[REDACTED_TOKEN]'),
    # Passwords in URLs / Connection strings
    (re.compile(r'(?i)(://[^:]+:)([^@]+)(@)'),
     r'\1[REDACTED_PASSWORD]\3'),
    (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']([^"\']+)["\']'),
     r'\1="[REDACTED_PASSWORD]"'),
    # Private Key blocks
    (re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----'),
     '[REDACTED_PRIVATE_KEY]'),
    # AWS / GCP / GitHub tokens
    (re.compile(r'(ghp_[A-Za-z0-9_]{36}|gho_[A-Za-z0-9_]{36}|github_pat_[A-Za-z0-9_]{82})'),
     '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'(AKIA[0-9A-Z]{16})'),
     '[REDACTED_AWS_KEY]'),
]


class SecretFilter:
    """Detects and redacts sensitive credentials and blocks sensitive files."""

    @staticmethod
    def is_blocked_path(relative_path: str) -> bool:
        """Check if path or any of its parents matches blocked directory or file pattern."""
        normalized = relative_path.replace("\\", "/").strip("/")
        parts = normalized.split("/")

        # Check directories
        for part in parts[:-1]:
            if part in BLOCKED_DIR_NAMES:
                return True

        filename = parts[-1]
        if filename in BLOCKED_DIR_NAMES:
            return True

        # Check binary extensions
        _, ext = os.path.splitext(filename.lower())
        if ext in BINARY_EXTENSIONS:
            return True

        # Check regex patterns
        for pattern in BLOCKED_FILE_PATTERNS:
            if re.match(pattern, filename, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def redact_text(content: str) -> str:
        """Redact secrets and credentials from source code or diff snippets."""
        if not content:
            return content

        result = content
        for pattern, replacement in REDACTION_PATTERNS:
            result = pattern.sub(replacement, result)

        return result
