# Release Gate Decision Logic — ShipSafe AI V2

## Overview
ShipSafe AI evaluates software changes using an objective, evidence-backed decision matrix rather than arbitrary statistical scores or unverified LLM impressions.

The Release Gate computes one of three authoritative statuses:
- **`READY`**: The change is safe to deploy to production.
- **`ATTENTION`**: The change contains non-blocking concerns or unverified risk items that require engineering review.
- **`BLOCKED`**: The change contains confirmed regressions, critical security flaws, or breaking contract mismatches that will cause production incidents.

---

## Decision Matrix

| Gate Status | Triggering Conditions | Required Action |
|---|---|---|
| **BLOCKED** | Any of:<br>1. **Critical Security Finding** (e.g., confirmed SQL injection, command execution, leaked credentials).<br>2. **Confirmed Blocking Requirement Violation** (e.g., hard contract breach on core requirement).<br>3. **Failing Test Suite** (any deterministic regression test failure in modified area).<br>4. **Unsafe Database Migration State** (unmigrated model, non-nullable column added without default, destructive column drop). | **Immediate Deployment Stop.**<br>Remediation required before release. |
| **ATTENTION** | Any of (with zero BLOCKED conditions):<br>1. **High-Severity Finding** not deemed immediately exploitable or fatal.<br>2. **Significant Test Coverage Gap** in newly introduced business logic.<br>3. **API Contract Mismatch** without breaking consumer compatibility.<br>4. **Documentation / Spec Discrepancy**.<br>5. **Database Impact** requiring manual verification. | **Engineering Review.**<br>Manual approval or patch recommendation. |
| **READY** | All of:<br>1. Zero Critical or High blocking security findings.<br>2. All relevant test suites executed and passed (100% pass rate).<br>3. All tracked requirement checks validated.<br>4. Database schema and migrations verified consistent.<br>5. No unverified or unconfirmed findings remaining. | **Approved for Release.**<br>Automated CI/CD promotion allowed. |

---

## Metric Integrity Rules
1. **No Hallucinated Pass Rates**: A pass rate cannot be displayed without executing the actual test runner (e.g., `pytest`, `npm test`, `mvn test`).
2. **Deterministic Evidence Priority**: Deterministic findings (e.g., test failures, unmigrated SQL columns, detected secret tokens) override any optimistic LLM assessment.
3. **No Metric Averaging**: High security risk is never "balanced out" by high test coverage. A single confirmed critical flaw strictly results in `BLOCKED`.
