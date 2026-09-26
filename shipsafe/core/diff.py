"""Diff parser and changed symbol extraction."""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from .secrets import SecretFilter


@dataclass
class DiffHunk:
    old_start: int
    old_length: int
    new_start: int
    new_length: int
    header: str
    lines: List[str] = field(default_factory=list)


@dataclass
class FileDiff:
    file_path: str
    status: str  # 'modified', 'added', 'deleted', 'renamed'
    additions: int = 0
    deletions: int = 0
    hunks: List[DiffHunk] = field(default_factory=list)
    changed_symbols: List[str] = field(default_factory=list)
    raw_patch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "status": self.status,
            "additions": self.additions,
            "deletions": self.deletions,
            "changed_symbols": self.changed_symbols,
            "raw_patch": self.raw_patch,
        }


class DiffParser:
    """Parses unified git diff into structured file diffs and extracts changed symbols."""

    # Regex patterns for Python, JS/TS, Java functions and classes
    SYMBOL_PATTERNS = [
        # Python def / class
        re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)"),
        # JS / TS function / class / const arrow
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("),
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"),
        # Java method / class
        re.compile(r"^\s*(?:public|protected|private|static|\s)+[\w<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*(?:public|protected|private|\s)+class\s+([A-Za-z_][A-Za-z0-9_]*)"),
    ]

    @classmethod
    def parse(cls, diff_text: str) -> List[FileDiff]:
        """Parse raw unified diff output."""
        if not diff_text:
            return []

        # Redact secrets before parsing
        clean_diff = SecretFilter.redact_text(diff_text)

        file_diffs: List[FileDiff] = []
        raw_files = re.split(r"(^diff --git )", clean_diff, flags=re.MULTILINE)

        chunks = []
        for i in range(1, len(raw_files), 2):
            chunks.append(raw_files[i] + raw_files[i + 1])

        for chunk in chunks:
            f_diff = cls._parse_single_file_diff(chunk)
            if f_diff and not SecretFilter.is_blocked_path(f_diff.file_path):
                file_diffs.append(f_diff)

        return file_diffs

    @classmethod
    def _parse_single_file_diff(cls, chunk: str) -> Optional[FileDiff]:
        lines = chunk.splitlines()
        if not lines:
            return None

        # Determine file path
        header_match = re.search(r"diff --git a/(.*?) b/(.*)", lines[0])
        if not header_match:
            return None

        file_path = header_match.group(2)
        status = "modified"

        # Check for new or deleted file
        for l in lines[:6]:
            if l.startswith("new file mode"):
                status = "added"
            elif l.startswith("deleted file mode"):
                status = "deleted"
            elif l.startswith("similarity index"):
                status = "renamed"

        additions = 0
        deletions = 0
        changed_symbols = set()
        hunks: List[DiffHunk] = []
        current_hunk: Optional[DiffHunk] = None

        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")

        for line in lines:
            m = hunk_header_re.match(line)
            if m:
                if current_hunk:
                    hunks.append(current_hunk)
                old_start = int(m.group(1))
                old_len = int(m.group(2) or 1)
                new_start = int(m.group(3))
                new_len = int(m.group(4) or 1)
                header_context = m.group(5) or ""

                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_length=old_len,
                    new_start=new_start,
                    new_length=new_len,
                    header=line
                )

                # Check symbol in hunk context header
                for pattern in cls.SYMBOL_PATTERNS:
                    sm = pattern.search(header_context)
                    if sm:
                        changed_symbols.add(sm.group(1))
                continue

            if current_hunk is not None:
                current_hunk.lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                    # Check added line for symbol definition
                    for pattern in cls.SYMBOL_PATTERNS:
                        sm = pattern.search(line[1:])
                        if sm:
                            changed_symbols.add(sm.group(1))
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
                    # Check deleted line for symbol definition
                    for pattern in cls.SYMBOL_PATTERNS:
                        sm = pattern.search(line[1:])
                        if sm:
                            changed_symbols.add(sm.group(1))

        if current_hunk:
            hunks.append(current_hunk)

        return FileDiff(
            file_path=file_path,
            status=status,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            changed_symbols=sorted(list(changed_symbols)),
            raw_patch=chunk
        )
