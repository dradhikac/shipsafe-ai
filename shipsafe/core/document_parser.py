"""Parses requirements (Markdown, PDF), documentation, and OpenAPI schemas."""

import json
import os
import re
from typing import Dict, List, Any, Optional
import yaml
from .secrets import SecretFilter


class DocumentParser:
    """Extracts structured requirements and API specifications from repository docs."""

    REQ_ID_PATTERNS = [
        re.compile(r"\b(R\d{3,4})\b", re.IGNORECASE),
        re.compile(r"\b(REQ-[A-Z0-9_-]+)\b", re.IGNORECASE),
        re.compile(r"\b(SPEC-[A-Z0-9_-]+)\b", re.IGNORECASE),
    ]

    @classmethod
    def parse_markdown_requirements(cls, file_path: str) -> List[Dict[str, Any]]:
        """Extract requirement sections and identifiers from a markdown file."""
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return []

        clean_content = SecretFilter.redact_text(content)
        requirements: List[Dict[str, Any]] = []

        # Split by markdown headers (# or ## or ###)
        sections = re.split(r"(^#{1,4}\s+.*$)", clean_content, flags=re.MULTILINE)
        current_title = os.path.basename(file_path)
        current_body = ""

        chunks = []
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                header = sections[i].strip()
                body = sections[i + 1] if i + 1 < len(sections) else ""
                chunks.append((header, body))
        else:
            chunks.append((current_title, clean_content))

        for header, body in chunks:
            req_ids = set()
            for pattern in cls.REQ_ID_PATTERNS:
                for match in pattern.finditer(header + " " + body):
                    req_ids.add(match.group(1).upper())

            if req_ids:
                for rid in sorted(list(req_ids)):
                    requirements.append({
                        "id": rid,
                        "title": header.lstrip("#").strip(),
                        "file": file_path,
                        "text": body.strip()[:1000],
                    })
            elif "requirement" in header.lower() or "acceptance criteria" in header.lower():
                requirements.append({
                    "id": f"DOC-{len(requirements)+1:03d}",
                    "title": header.lstrip("#").strip(),
                    "file": file_path,
                    "text": body.strip()[:1000],
                })

        return requirements

    @classmethod
    def parse_pdf_requirements(cls, file_path: str) -> List[Dict[str, Any]]:
        """Extract text and requirements from a PDF document."""
        if not os.path.exists(file_path):
            return []

        text = ""
        # Try pypdf or PyPDF2 if available
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        except Exception:
            # Fallback text extraction or placeholder
            try:
                with open(file_path, "rb") as f:
                    raw = f.read().decode("latin-1", errors="ignore")
                    text = " ".join(re.findall(r"\(([\w\s.,;:!-]+)\)\s*Tj", raw))
            except Exception:
                text = ""

        if not text:
            return []

        req_ids = set()
        for pattern in cls.REQ_ID_PATTERNS:
            for match in pattern.finditer(text):
                req_ids.add(match.group(1).upper())

        return [
            {
                "id": rid,
                "title": f"PDF Requirement {rid}",
                "file": file_path,
                "text": text[:1500],
            }
            for rid in sorted(list(req_ids))
        ]

    @classmethod
    def parse_openapi(cls, file_path: str) -> List[Dict[str, Any]]:
        """Parse OpenAPI / Swagger JSON or YAML specification."""
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if file_path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
        except Exception:
            return []

        if not isinstance(data, dict):
            return []

        paths = data.get("paths", {})
        endpoints = []

        for path_url, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, details in methods.items():
                if method.lower() in ("get", "post", "put", "delete", "patch", "options", "head"):
                    endpoints.append({
                        "path": path_url,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "operation_id": details.get("operationId", ""),
                        "responses": list(details.get("responses", {}).keys()),
                        "spec_file": file_path,
                    })

        return endpoints
