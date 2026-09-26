"""Deterministic test execution and coverage collection."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class TestCaseFailure:
    test_name: str
    message: str
    file_path: Optional[str] = None
    line: Optional[int] = None


@dataclass
class TestRunResult:
    __test__ = False
    framework: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    failures: List[TestCaseFailure] = field(default_factory=list)
    coverage_percent: Optional[float] = None
    raw_output: str = ""
    exit_code: int = 0

    @property
    def is_all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.total_tests > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "duration_seconds": self.duration_seconds,
            "is_all_passed": self.is_all_passed,
            "coverage_percent": self.coverage_percent,
            "failures": [
                {
                    "test_name": f.test_name,
                    "message": f.message,
                    "file_path": f.file_path,
                    "line": f.line,
                }
                for f in self.failures
            ],
            "exit_code": self.exit_code,
        }


class TestRunner:
    __test__ = False
    """Executes tests deterministically for supported frameworks."""

    def __init__(self, repo_dir: str):
        self.repo_dir = os.path.abspath(repo_dir)

    def run(self, framework: Optional[str] = None, timeout_seconds: int = 30) -> TestRunResult:
        """Run tests using the specified or auto-detected framework."""
        if os.environ.get("SHIPSAFE_INNER_TEST_RUN") == "1":
            return TestRunResult(
                framework="pytest",
                total_tests=0,
                passed=0,
                failed=0,
                raw_output="Skipped nested test runner execution to avoid recursion.",
                exit_code=0
            )

        if not framework:
            framework = self._detect_framework()

        if framework == "pytest":
            return self._run_pytest(timeout_seconds)
        elif framework == "npm":
            return self._run_npm(timeout_seconds)
        else:
            return TestRunResult(
                framework="unknown",
                raw_output="No supported test runner detected.",
                exit_code=0
            )

    def _detect_framework(self) -> str:
        if os.path.exists(os.path.join(self.repo_dir, "pytest.ini")) or \
           os.path.exists(os.path.join(self.repo_dir, "conftest.py")) or \
           os.path.exists(os.path.join(self.repo_dir, "tests")):
            return "pytest"
        if os.path.exists(os.path.join(self.repo_dir, "package.json")):
            return "npm"
        return "pytest"

    def _run_pytest(self, timeout: int) -> TestRunResult:
        """Run pytest using current python interpreter."""
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
        
        # Check if pytest-cov is available
        try:
            subprocess.run([sys.executable, "-m", "pytest", "--cov-help"], capture_output=True)
            has_cov = True
        except Exception:
            has_cov = False

        if has_cov:
            cmd.extend(["--cov=.", "--cov-report=term-missing"])

        env = os.environ.copy()
        env["SHIPSAFE_INNER_TEST_RUN"] = "1"
        env["PYTHONPATH"] = f"{self.repo_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            raw = proc.stdout + "\n" + proc.stderr
            return self._parse_pytest_output(raw, proc.returncode)
        except subprocess.TimeoutExpired:
            return TestRunResult(
                framework="pytest",
                raw_output=f"Pytest execution timed out after {timeout} seconds.",
                exit_code=124,
                errors=1,
            )
        except Exception as e:
            return TestRunResult(
                framework="pytest",
                raw_output=f"Failed to execute pytest: {str(e)}",
                exit_code=1,
                errors=1,
            )

    def _parse_pytest_output(self, output: str, exit_code: int) -> TestRunResult:
        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        duration = 0.0
        failures: List[TestCaseFailure] = []
        coverage = None

        # Pytest summary line regex: "=== 5 passed, 1 failed in 0.42s ==="
        summary_m = re.search(r"=+\s*(.*?)\s+in\s+([\d\.]+s?)\s*=+", output)
        if summary_m:
            summary_str = summary_m.group(1)
            duration_str = summary_m.group(2).replace("s", "")
            try:
                duration = float(duration_str)
            except ValueError:
                pass

            p_m = re.search(r"(\d+)\s+passed", summary_str)
            if p_m:
                passed = int(p_m.group(1))

            f_m = re.search(r"(\d+)\s+failed", summary_str)
            if f_m:
                failed = int(f_m.group(1))

            e_m = re.search(r"(\d+)\s+error", summary_str)
            if e_m:
                errors = int(e_m.group(1))

            s_m = re.search(r"(\d+)\s+skipped", summary_str)
            if s_m:
                skipped = int(s_m.group(1))

        # Extract failed test names
        for line in output.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                parts = line.split(" ", 2)
                test_name = parts[1] if len(parts) > 1 else line
                msg = parts[2] if len(parts) > 2 else ""
                failures.append(TestCaseFailure(test_name=test_name, message=msg))

        # Coverage line: "TOTAL ... 85%"
        cov_m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if cov_m:
            coverage = float(cov_m.group(1))

        total = passed + failed + errors + skipped
        return TestRunResult(
            framework="pytest",
            total_tests=total,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration_seconds=duration,
            failures=failures,
            coverage_percent=coverage,
            raw_output=output,
            exit_code=exit_code,
        )

    def _run_npm(self, timeout: int) -> TestRunResult:
        cmd = ["npm", "test"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                shell=True,
            )
            raw = proc.stdout + "\n" + proc.stderr
            return TestRunResult(
                framework="npm",
                raw_output=raw,
                exit_code=proc.returncode,
                total_tests=1 if proc.returncode == 0 else 0,
                passed=1 if proc.returncode == 0 else 0,
                failed=1 if proc.returncode != 0 else 0,
            )
        except Exception as e:
            return TestRunResult(framework="npm", raw_output=str(e), exit_code=1, errors=1)
