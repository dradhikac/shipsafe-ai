# GitHub Continuous Monitoring Specification — ShipSafe AI V2

## Overview
ShipSafe AI operates as an event-driven continuous release safety monitor. Rather than running inefficient background polling or waiting for manual triggers, ShipSafe connects directly to GitHub Webhooks.

---

## Webhook Architecture

```
+------------------+         HMAC-SHA256 Signed POST         +--------------------+
|  GitHub Webhook  |  ===================================>   |  FastAPI Endpoint  |
|                  |     X-Hub-Signature-256                 |  /webhooks/github  |
|                  |     X-GitHub-Delivery                   +---------+----------+
|                  |     X-GitHub-Event                                |
+------------------+                                                   | 1. Verify Secret
                                                                       | 2. Check Deduplication
                                                                       | 3. Persist Event
                                                                       | 4. Return HTTP 202
                                                                       v
                                                             +--------------------+
                                                             | SQLite/PostgreSQL  |
                                                             |  webhook_events    |
                                                             |  analysis_runs     |
                                                             +---------+----------+
                                                                       |
                                                                       | Background Task
                                                                       v
                                                             +--------------------+
                                                             |  Analysis Worker   |
                                                             |  worker/worker.py  |
                                                             +--------------------+
```

---

## Supported GitHub Events

### 1. `push`
- **Trigger**: Developer pushes commits to a monitored branch (e.g., `main`, `release/*`, `staging`).
- **ShipSafe Action**:
  - Extracts repository clone URL, base commit SHA (`before`), and head commit SHA (`after`).
  - Creates a change analysis job.
  - Generates evidence pack focusing on the pushed commit delta.

### 2. `pull_request`
- **Actions**:
  - `opened`: Triggers full release-readiness analysis on PR branch against base branch.
  - `synchronize`: Triggers re-analysis when new commits are pushed to the PR.
  - `reopened`: Triggers re-validation of PR state.
  - `closed`: If merged, records final release audit; if closed unmerged, marks run as archived.
- **ShipSafe Action**: Full comprehensive analysis across all 5 specialist agents and release gate determination.

---

## Security & Verification

### Secret Verification
All incoming requests to `/webhooks/github` are validated using HMAC-SHA256:
```python
import hmac
import hashlib

def verify_github_signature(payload_bytes: bytes, secret: str, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hash = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    actual_hash = signature_header.split("sha256=")[1]
    return hmac.compare_digest(expected_hash, actual_hash)
```
If verification fails, FastAPI immediately responds with `401 Unauthorized` and does not process the body.

### Delivery ID Deduplication
GitHub guarantees at-least-once delivery, which can result in duplicate webhook calls.
- Every webhook request includes the `X-GitHub-Delivery` header (a unique UUID).
- ShipSafe records this `delivery_id` in `webhook_events`.
- If a delivery ID is already recorded, the endpoint logs the duplicate, returns `200 OK` (or `202 Accepted`) with `{"status": "duplicate_ignored"}`, and does NOT create a redundant analysis run.

---

## Webhook Handler Lifecycle
1. **Raw Body Read**: Read raw bytes before JSON parsing for cryptographic signature verification.
2. **Signature Check**: Compare `X-Hub-Signature-256` with HMAC of the payload using `GITHUB_WEBHOOK_SECRET`.
3. **Header Inspection**: Verify event type is supported (`push`, `pull_request`). Unsupported events receive `200 OK` with `{"status": "ignored_event_type"}`.
4. **Idempotency Guard**: Query database for `delivery_id`. Reject duplicates gracefully.
5. **Event Persistence**: Insert record into `webhook_events` table.
6. **Job Enqueue**: Insert job into `analysis_runs` with status `PENDING`.
7. **Immediate Acknowledgment**: Return `202 Accepted` within 200ms to satisfy GitHub's timeout SLA.
8. **Asynchronous Execution**: Worker claims `PENDING` job from database and begins analysis.
