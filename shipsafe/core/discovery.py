"""Deterministic repository discovery engine for arbitrary projects."""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from .secrets import SecretFilter


class ProjectDiscovery:
    """Discovers project types, test frameworks, requirements, APIs, schemas, and dependencies."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def scan(self) -> Dict[str, Any]:
        """Perform comprehensive deterministic scan of repository structure."""
        all_files = self._list_safe_files()

        languages = self._detect_languages(all_files)
        test_frameworks, test_files = self._discover_tests(all_files)
        requirements_docs = self._discover_requirements(all_files)
        api_definitions = self._discover_apis(all_files)
        schemas_and_migrations = self._discover_database(all_files)
        dependency_manifests = self._discover_dependencies(all_files)

        return {
            "root_dir": self.root_dir,
            "total_files": len(all_files),
            "languages": languages,
            "is_mixed": len(languages) > 1,
            "test_frameworks": test_frameworks,
            "test_files": test_files,
            "requirements_docs": requirements_docs,
            "api_definitions": api_definitions,
            "database": schemas_and_migrations,
            "dependency_manifests": dependency_manifests,
        }

    def _list_safe_files(self) -> List[str]:
        """List all non-blocked relative file paths."""
        safe_files = []
        for root, dirs, files in os.walk(self.root_dir):
            rel_root = os.path.relpath(root, self.root_dir).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""

            # Prune blocked directories in-place
            dirs[:] = [
                d for d in dirs
                if not SecretFilter.is_blocked_path(f"{rel_root}/{d}" if rel_root else d)
            ]

            for f in files:
                rel_path = f"{rel_root}/{f}" if rel_root else f
                if not SecretFilter.is_blocked_path(rel_path):
                    safe_files.append(rel_path)

        return safe_files

    def _detect_languages(self, files: List[str]) -> List[str]:
        """Detect primary languages in the repository."""
        counts = {"python": 0, "javascript": 0, "typescript": 0, "java": 0, "sql": 0}
        for f in files:
            ext = os.path.splitext(f.lower())[1]
            if ext == ".py":
                counts["python"] += 1
            elif ext in (".js", ".jsx", ".mjs"):
                counts["javascript"] += 1
            elif ext in (".ts", ".tsx"):
                counts["typescript"] += 1
            elif ext == ".java":
                counts["java"] += 1
            elif ext == ".sql":
                counts["sql"] += 1

        detected = [lang for lang, c in counts.items() if c > 0]
        return sorted(detected, key=lambda l: counts[l], reverse=True)

    def _discover_tests(self, files: List[str]) -> tuple[List[str], List[str]]:
        """Identify test frameworks and test files."""
        frameworks = set()
        test_files = []

        test_file_re = re.compile(r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+\.test\.[jt]sx?|[^/]+\.spec\.[jt]sx?|Test[^/]+\.java)$", re.IGNORECASE)

        for f in files:
            lower = f.lower()
            if test_file_re.search(f) or "/tests/" in lower or "/test/" in lower:
                test_files.append(f)

            if lower.endswith("conftest.py") or "pytest" in lower:
                frameworks.add("pytest")
            elif lower.endswith("pom.xml") or lower.endswith("build.gradle"):
                frameworks.add("junit")
            elif "jest.config" in lower:
                frameworks.add("jest")
            elif "vitest.config" in lower:
                frameworks.add("vitest")

        if not frameworks and any(f.endswith(".py") for f in test_files):
            frameworks.add("pytest")

        return sorted(list(frameworks)), sorted(test_files)

    def _discover_requirements(self, files: List[str]) -> List[str]:
        """Find requirement, specification, and architectural documentation."""
        req_files = []
        for f in files:
            lower = f.lower()
            if lower.startswith("requirements/") or lower.startswith("specs/") or "requirement" in lower:
                if lower.endswith((".md", ".txt", ".pdf")):
                    req_files.append(f)
            elif lower.endswith("readme.md"):
                req_files.append(f)

        return sorted(req_files)

    def _discover_apis(self, files: List[str]) -> List[Dict[str, Any]]:
        """Identify OpenAPI schemas and API route definitions."""
        apis = []
        for f in files:
            lower = f.lower()
            if any(name in lower for name in ["openapi.json", "openapi.yaml", "swagger.json", "swagger.yaml"]):
                apis.append({"type": "openapi_spec", "file": f})
            elif "/routes/" in lower or "/api/" in lower or "/controllers/" in lower:
                apis.append({"type": "route_handler", "file": f})

        return apis

    def _discover_database(self, files: List[str]) -> Dict[str, List[str]]:
        """Identify database schema definitions and migration scripts."""
        migrations = []
        schemas = []
        models = []

        for f in files:
            lower = f.lower()
            if "migration" in lower or "/migrations/" in lower:
                migrations.append(f)
            elif lower.endswith(".sql") or "schema" in lower:
                schemas.append(f)
            elif "model" in lower or "/models/" in lower or "entity" in lower:
                models.append(f)

        return {
            "migrations": sorted(migrations),
            "schemas": sorted(schemas),
            "models": sorted(models),
        }

    def _discover_dependencies(self, files: List[str]) -> List[str]:
        """Identify dependency and build manifests."""
        manifest_names = {
            "requirements.txt", "pipfile", "pyproject.toml", "setup.py",
            "package.json", "pom.xml", "build.gradle", "cargo.toml", "go.mod"
        }
        manifests = []
        for f in files:
            if os.path.basename(f).lower() in manifest_names:
                manifests.append(f)
        return sorted(manifests)
