"""Simulate GitHub Webhooks locally for testing push and pull_request events."""

import argparse
import hashlib
import hmac
import json
import os
import sys
import uuid
import httpx


def generate_push_payload(repo_name: str, branch: str, local_path: str) -> dict:
    return {
        "ref": f"refs/heads/{branch}",
        "before": "6d92a10b42f10b2c34a984bc0f123456789abcde",
        "after": "9f8e7d6c5b4a3210fedcba987654321012345678",
        "repository": {
            "name": repo_name,
            "full_name": f"dradhikac/{repo_name}",
            "clone_url": f"https://github.com/dradhikac/{repo_name}.git",
            "default_branch": "main",
        },
        "pusher": {
            "name": "developer",
            "email": "dev@shipsafe.internal"
        },
        "local_path": os.path.abspath(local_path)
    }


def generate_pr_payload(repo_name: str, branch: str, local_path: str, action: str = "opened") -> dict:
    return {
        "action": action,
        "number": 42,
        "pull_request": {
            "title": "feat: introduce billing adjustments and updated constraints",
            "state": "open",
            "head": {
                "ref": branch,
                "sha": "9f8e7d6c5b4a3210fedcba987654321012345678"
            },
            "base": {
                "ref": "main",
                "sha": "6d92a10b42f10b2c34a984bc0f123456789abcde"
            }
        },
        "repository": {
            "name": repo_name,
            "full_name": f"dradhikac/{repo_name}",
            "clone_url": f"https://github.com/dradhikac/{repo_name}.git",
            "default_branch": "main",
        },
        "local_path": os.path.abspath(local_path)
    }


def send_webhook(url: str, event_type: str, payload: dict, secret: str = ""):
    delivery_id = str(uuid.uuid4())
    body_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": event_type,
        "X-GitHub-Delivery": delivery_id,
        "User-Agent": "GitHub-Hookshot/shipsafe-sim",
    }

    if secret:
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = sig

    print(f"\n[Simulator] Sending {event_type.upper()} event to {url}...")
    print(f"[Simulator] Delivery ID: {delivery_id}")
    print(f"[Simulator] Target Repository: {payload.get('repository', {}).get('name')}")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, content=body_bytes)
            print(f"[Simulator] Response HTTP Status: {resp.status_code}")
            try:
                print(f"[Simulator] Response Body:\n{json.dumps(resp.json(), indent=2)}")
            except Exception:
                print(f"[Simulator] Response Text:\n{resp.text}")
    except httpx.ConnectError:
        print(f"[Simulator Error] Could not connect to {url}. Is the FastAPI server running on port 8000?", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Simulate GitHub push or pull_request webhooks locally.")
    parser.add_argument("--event", choices=["push", "pull_request"], default="push", help="GitHub event type")
    parser.add_argument("--repo", default="carehub-appointment-service", help="Repository name")
    parser.add_argument("--path", default="examples/carehub", help="Local directory path of target repository")
    parser.add_argument("--branch", default="feature/billing-v2", help="Branch name")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/github", help="FastAPI webhook endpoint URL")
    parser.add_argument("--secret", default=os.environ.get("GITHUB_WEBHOOK_SECRET", ""), help="Webhook HMAC secret")

    args = parser.parse_args()

    if args.event == "push":
        payload = generate_push_payload(args.repo, args.branch, args.path)
    else:
        payload = generate_pr_payload(args.repo, args.branch, args.path)

    send_webhook(args.url, args.event, payload, args.secret)


if __name__ == "__main__":
    main()
