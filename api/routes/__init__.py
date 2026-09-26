"""FastAPI route registration."""

from .health import router as health_router
from .webhooks import router as webhooks_router
from .repositories import router as repositories_router
from .runs import router as runs_router
from .remediation import router as remediation_router

__all__ = [
    "health_router",
    "webhooks_router",
    "repositories_router",
    "runs_router",
    "remediation_router",
]
