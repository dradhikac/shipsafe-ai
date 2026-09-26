"""Deterministic repository discovery engine for arbitrary projects."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional
from .secrets import SecretFilter


@dataclass
class RepositoryProfile:
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    test_frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    api_style: List[str] = field(default_factory=list)
    dependency_manifests: List[str] = field(default_factory=list)
    migration_system: List[str] = field(default_factory=list)

    @property
    def has_database(self) -> bool:
        return bool(self.databases or self.migration_system)

    @property
    def has_api(self) -> bool:
        return bool(self.api_style or self.frameworks)

    @property
    def has_tests(self) -> bool:
        return bool(self.test_frameworks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "languages": self.languages,
            "frameworks": self.frameworks,
            "test_frameworks": self.test_frameworks,
            "databases": self.databases,
            "api_style": self.api_style,
            "dependency_manifests": self.dependency_manifests,
            "migration_system": self.migration_system,
            "has_database": self.has_database,
            "has_api": self.has_api,
            "has_tests": self.has_tests,
        }


class ProjectDiscovery:
    """Discovers project types, test frameworks, requirements, APIs, schemas, and dependencies."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def scan(self) -> Dict[str, Any]:
        """Perform comprehensive deterministic scan of repository structure."""
        all_files = self._list_safe_files()

        languages = self._detect_languages(all_files)
        frameworks = self._detect_frameworks(all_files)
        test_frameworks, test_files = self._discover_tests(all_files)
        requirements_docs = self._discover_requirements(all_files)
        api_definitions, api_style = self._discover_apis(all_files)
        schemas_and_migrations, databases, migration_system = self._discover_database(all_files)
        dependency_manifests = self._discover_dependencies(all_files)

        profile = RepositoryProfile(
            languages=languages,
            frameworks=frameworks,
            test_frameworks=test_frameworks,
            databases=databases,
            api_style=api_style,
            dependency_manifests=dependency_manifests,
            migration_system=migration_system,
        )

        return {
            "root_dir": self.root_dir,
            "total_files": len(all_files),
            "languages": languages,
            "is_mixed": len(languages) > 1,
            "frameworks": frameworks,
            "test_frameworks": test_frameworks,
            "test_files": test_files,
            "requirements_docs": requirements_docs,
            "api_definitions": api_definitions,
            "api_style": api_style,
            "database": schemas_and_migrations,
            "databases": databases,
            "migration_system": migration_system,
            "dependency_manifests": dependency_manifests,
            "profile": profile.to_dict(),
        }

    def get_profile(self) -> RepositoryProfile:
        """Convenience method returning the structured RepositoryProfile."""
        data = self.scan()
        p = data["profile"]
        return RepositoryProfile(
            languages=p["languages"],
            frameworks=p["frameworks"],
            test_frameworks=p["test_frameworks"],
            databases=p["databases"],
            api_style=p["api_style"],
            dependency_manifests=p["dependency_manifests"],
            migration_system=p["migration_system"],
        )

    def _list_safe_files(self) -> List[str]:
        """List all non-blocked relative file paths."""
        safe_files = []
        for root, dirs, files in os.walk(self.root_dir):
            rel_root = os.path.relpath(root, self.root_dir).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""

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
        counts = {"python": 0, "javascript": 0, "typescript": 0, "java": 0, "sql": 0, "go": 0, "rust": 0}
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
            elif ext == ".go":
                counts["go"] += 1
            elif ext == ".rs":
                counts["rust"] += 1

        detected = [lang for lang, c in counts.items() if c > 0]
        return sorted(detected, key=lambda l: counts[l], reverse=True)

    def _detect_frameworks(self, files: List[str]) -> List[str]:
        """Detect web/application frameworks based on imports, manifests, or configuration."""
        frameworks = set()
        for f in files:
            lower = f.lower()
            basename = os.path.basename(lower)

            # Python
            if lower.endswith(".py"):
                # Fast search in short files or file names
                if "fastapi" in lower:
                    frameworks.add("FastAPI")
                elif "flask" in lower:
                    frameworks.add("Flask")
                elif "django" in lower:
                    frameworks.add("Django")

            # JS / Node
            elif basename == "package.json":
                try:
                    full_p = os.path.join(self.root_dir, f)
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        if '"express"' in content:
                            frameworks.add("Express")
                        if '"react"' in content:
                            frameworks.add("React")
                        if '"next"' in content:
                            frameworks.add("Next.js")
                        if '"@nestjs/core"' in content:
                            frameworks.add("NestJS")
                except Exception:
                    pass

            # Java
            elif basename in ("pom.xml", "build.gradle", "build.gradle.kts"):
                try:
                    full_p = os.path.join(self.root_dir, f)
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        if "spring-boot" in content or "springframework" in content:
                            frameworks.add("Spring")
                except Exception:
                    pass

        return sorted(list(frameworks))

    def _discover_tests(self, files: List[str]) -> tuple[List[str], List[str]]:
        """Identify test frameworks and test files."""
        frameworks = set()
        test_files = []

        test_file_re = re.compile(
            r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+\.test\.[jt]sx?|[^/]+\.spec\.[jt]sx?|Test[^/]+\.java)$",
            re.IGNORECASE,
        )

        for f in files:
            lower = f.lower()
            if test_file_re.search(f) or "/tests/" in lower or "/test/" in lower:
                test_files.append(f)

            if lower.endswith("conftest.py") or "pytest" in lower:
                frameworks.add("pytest")
            elif lower.endswith("pom.xml") or lower.endswith("build.gradle"):
                frameworks.add("junit")
            elif "jest.config" in lower or ".test." in lower:
                frameworks.add("jest")
            elif "vitest.config" in lower:
                frameworks.add("vitest")

        if not frameworks and any(f.endswith(".py") for f in test_files):
            frameworks.add("pytest")

        return sorted(list(frameworks)), sorted(test_files)

    def _discover_requirements(self, files: List[str]) -> List[str]:
        """Find explicit requirement, specification, and architectural documentation."""
        req_files = []
        for f in files:
            lower = f.lower()
            # Must be an explicit requirements or specs document, NOT general README
            if (
                lower.startswith("requirements/")
                or lower.startswith("specs/")
                or lower.startswith("docs/requirements")
                or "requirement" in lower
                or "spec" in lower
            ):
                if lower.endswith((".md", ".txt", ".pdf")):
                    req_files.append(f)

        return sorted(req_files)

    def _discover_apis(self, files: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Identify OpenAPI schemas, API route definitions, and API architectural style."""
        apis = []
        styles = set()
        for f in files:
            lower = f.lower()
            if any(name in lower for name in ["openapi.json", "openapi.yaml", "swagger.json", "swagger.yaml"]):
                apis.append({"type": "openapi_spec", "file": f})
                styles.add("REST")
                styles.add("OpenAPI")
            elif "/routes/" in lower or "/api/" in lower or "/controllers/" in lower or "route" in lower:
                apis.append({"type": "route_handler", "file": f})
                styles.add("REST")
            elif lower.endswith(".graphql") or lower.endswith(".gql"):
                apis.append({"type": "graphql_schema", "file": f})
                styles.add("GraphQL")
            elif lower.endswith(".proto"):
                apis.append({"type": "proto_spec", "file": f})
                styles.add("gRPC")

        return apis, sorted(list(styles))

    def _discover_database(self, files: List[str]) -> tuple[Dict[str, List[str]], List[str], List[str]]:
        """Identify database schema definitions, migration scripts, databases, and migration tools."""
        migrations = []
        schemas = []
        models = []
        databases = set()
        migration_systems = set()

        for f in files:
            lower = f.lower()
            basename = os.path.basename(lower)

            if "migration" in lower or "/migrations/" in lower or basename.startswith("alembic"):
                migrations.append(f)
                if "alembic" in lower:
                    migration_systems.add("Alembic")
                elif "flyway" in lower:
                    migration_systems.add("Flyway")
                elif "prisma" in lower:
                    migration_systems.add("Prisma")
                else:
                    migration_systems.add("SQL-Migrations")

            if lower.endswith(".sql") or "schema" in lower:
                schemas.append(f)
                if lower.endswith(".sql"):
                    databases.add("SQL")

            if "model" in lower or "/models/" in lower or "entity" in lower:
                models.append(f)

            # Check database engine specifics
            if "sqlite" in lower:
                databases.add("SQLite")
            elif "postgres" in lower or "psql" in lower:
                databases.add("PostgreSQL")
            elif "mysql" in lower:
                databases.add("MySQL")
            elif "mongodb" in lower or "mongo" in lower:
                databases.add("MongoDB")

        # Check dependency manifests for DB libraries
        for f in files:
            bname = os.path.basename(f).lower()
            if bname in ("requirements.txt", "pyproject.toml", "package.json"):
                try:
                    full_p = os.path.join(self.root_dir, f)
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                        txt = fh.read().lower()
                        if "sqlalchemy" in txt:
                            databases.add("SQLAlchemy")
                        if "psycopg" in txt or "pg" in txt:
                            databases.add("PostgreSQL")
                        if "sqlite3" in txt:
                            databases.add("SQLite")
                        if "prisma" in txt:
                            databases.add("Prisma")
                            migration_systems.add("Prisma")
                        if "alembic" in txt:
                            migration_systems.add("Alembic")
                except Exception:
                    pass

        return (
            {
                "migrations": sorted(migrations),
                "schemas": sorted(schemas),
                "models": sorted(models),
            },
            sorted(list(databases)),
            sorted(list(migration_systems)),
        )

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

