"""FastAPI application entrypoint for ShipSafe AI V2."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shipsafe.database import init_db
from api.routes import (
    health_router,
    webhooks_router,
    repositories_router,
    runs_router,
    remediation_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield


app = FastAPI(
    title="ShipSafe AI V2 — Continuous Release Safety Monitor API",
    description="Event-driven API for continuous repository monitoring, Grok agent orchestration, and release gating.",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for local dashboards and webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(repositories_router)
app.include_router(runs_router)
app.include_router(remediation_router)


@app.get("/")
def root():
    return {
        "product": "ShipSafe AI V2",
        "tagline": "Continuous Release Safety Monitor",
        "docs_url": "/docs",
        "health_url": "/health",
    }
