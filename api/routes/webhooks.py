"""GitHub Webhook receiver for push and pull_request events."""

import json
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import Optional

from shipsafe.database import get_db, WebhookEvent, AnalysisRun, Repository
from api.security import verify_github_signature

router = APIRouter(tags=["Webhooks"])

SUPPORTED_EVENTS = {"push", "pull_request"}


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db)
):
    """
    Ingest GitHub push and pull_request webhooks, verify HMAC signature,
    deduplicate using delivery ID, persist event, and enqueue analysis job.
    """
    # 1. Read raw request body
    body_bytes = await request.body()

    # 2. Verify signature
    if not verify_github_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing GitHub webhook HMAC signature."
        )

    # 3. Read headers
    event_type = x_github_event or "push"
    delivery_id = x_github_delivery or f"dev-delivery-{int(request.state.timestamp or 0) if hasattr(request.state, 'timestamp') else 'local'}"

    # 4. Check if event is supported
    if event_type not in SUPPORTED_EVENTS:
        return {
            "status": "ignored",
            "message": f"Unsupported GitHub event type '{event_type}'. Monitored: {list(SUPPORTED_EVENTS)}"
        }

    # 5. Parse JSON payload
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload.")

    # 6. Deduplicate using delivery ID
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.delivery_id == delivery_id).first()
    if existing_event:
        return {
            "status": "duplicate_ignored",
            "message": f"Webhook delivery ID '{delivery_id}' has already been processed.",
            "delivery_id": delivery_id
        }

    # 7. Persist WebhookEvent
    webhook_event = WebhookEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        payload=payload,
        processed=False
    )
    db.add(webhook_event)
    db.flush()

    # 8. Extract repository info and branch / SHAs
    repo_data = payload.get("repository", {})
    repo_name = repo_data.get("name") or repo_data.get("full_name") or "monitored-repo"
    repo_url = repo_data.get("clone_url") or repo_data.get("html_url") or "local"

    # Find or create registered repository
    repo_record = db.query(Repository).filter(
        (Repository.name == repo_name) | (Repository.repo_url == repo_url)
    ).first()

    if not repo_record:
        repo_record = Repository(
            name=repo_name,
            repo_url=repo_url,
            local_path=payload.get("local_path"),
            default_branch=repo_data.get("default_branch", "main"),
            is_active=True
        )
        db.add(repo_record)
        db.flush()

    # Parse branch and commit SHAs
    branch = "main"
    base_sha = None
    head_sha = None

    if event_type == "push":
        ref = payload.get("ref", "")
        branch = ref.split("/")[-1] if "/" in ref else (ref or "main")
        base_sha = payload.get("before")
        head_sha = payload.get("after")
    elif event_type == "pull_request":
        pr = payload.get("pull_request", {})
        branch = pr.get("head", {}).get("ref", "pr-branch")
        base_sha = pr.get("base", {}).get("sha")
        head_sha = pr.get("head", {}).get("sha")

    # 9. Create AnalysisRun job
    analysis_run = AnalysisRun(
        repository_id=repo_record.id,
        webhook_event_id=webhook_event.id,
        event_type=event_type,
        branch=branch,
        base_sha=base_sha,
        head_sha=head_sha,
        status="PENDING",
        release_status="PENDING",
        summary={"delivery_id": delivery_id}
    )
    db.add(analysis_run)
    db.commit()

    return {
        "status": "accepted",
        "message": "Webhook received and analysis job enqueued.",
        "delivery_id": delivery_id,
        "run_id": analysis_run.id,
        "repository": repo_record.name,
        "event_type": event_type,
        "branch": branch,
    }
