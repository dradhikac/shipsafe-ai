"""Repository management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shipsafe.database import get_db, Repository, AnalysisRun

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


class RepositoryCreate(BaseModel):
    name: str
    repo_url: str
    local_path: Optional[str] = None
    default_branch: str = "main"


class RepositoryResponse(BaseModel):
    id: int
    name: str
    repo_url: str
    local_path: Optional[str]
    default_branch: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=List[RepositoryResponse])
def list_repositories(db: Session = Depends(get_db)):
    """List all registered repositories."""
    return db.query(Repository).order_by(Repository.id.asc()).all()


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)):
    """Register a new repository for continuous monitoring."""
    existing = db.query(Repository).filter(Repository.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository '{payload.name}' is already registered."
        )

    repo = Repository(
        name=payload.name,
        repo_url=payload.repo_url,
        local_path=payload.local_path,
        default_branch=payload.default_branch,
        is_active=True
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.post("/{repo_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def trigger_repository_analysis(repo_id: int, branch: Optional[str] = None, db: Session = Depends(get_db)):
    """Manually enqueue an analysis run for a registered repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    target_branch = branch or repo.default_branch

    run = AnalysisRun(
        repository_id=repo.id,
        event_type="manual",
        branch=target_branch,
        status="PENDING",
        release_status="PENDING",
        summary={"trigger": "manual_api"}
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "status": "accepted",
        "message": f"Manual analysis job enqueued for repository '{repo.name}'.",
        "run_id": run.id,
        "branch": target_branch,
    }
