"""Security and HMAC verification for GitHub Webhooks."""

import hmac
import hashlib
import os
from typing import Optional


def verify_github_signature(payload_bytes: bytes, signature_header: Optional[str], secret: Optional[str] = None) -> bool:
    """
    Verify GitHub webhook signature using HMAC-SHA256.
    If secret is not set, allows development mode if APP_ENV != 'production'.
    """
    secret = secret or os.environ.get("GITHUB_WEBHOOK_SECRET")
    app_env = os.environ.get("APP_ENV", "development")

    # If in development and no secret configured, allow unauthenticated for local testing
    if not secret:
        if app_env == "production":
            return False
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    actual_signature = signature_header.split("sha256=")[1].strip()
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, actual_signature)
