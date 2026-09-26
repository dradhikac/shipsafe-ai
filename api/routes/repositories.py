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


class RepositoryConnect(BaseModel):
    url: str
    branch: Optional[str] = None
    display_name: Optional[str] = None
    token: Optional[str] = None


class MonitoringUpdate(BaseModel):
    enabled: bool


class BranchSelect(BaseModel):
    branch: str


class RepositoryResponse(BaseModel):
    id: int
    provider: Optional[str] = "github"
    owner: Optional[str] = None
    name: str
    repo_url: str
    local_path: Optional[str] = None
    default_branch: str = "main"
    selected_branch: Optional[str] = "main"
    available_branches: Optional[List[str]] = []
    monitoring_enabled: Optional[bool] = False
    latest_commit_sha: Optional[str] = None
    files_count: Optional[int] = 0
    is_active: bool = True

    model_config = {"from_attributes": True}


@router.get("", response_model=List[RepositoryResponse])
def list_repositories(db: Session = Depends(get_db)):
    """List all registered repositories."""
    return db.query(Repository).order_by(Repository.id.asc()).all()


@router.post("/connect", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def connect_repository(payload: RepositoryConnect, db: Session = Depends(get_db)):
    """Connect a real GitHub repository: validate, clone/fetch, inspect branches, and persist."""
    from shipsafe.core.repo_manager import RepositoryManager
    try:
        repo = RepositoryManager.connect_repository(
            db=db,
            url=payload.url,
            branch=payload.branch,
            display_name=payload.display_name,
            token=payload.token
        )
        return repo
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(pe))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Repository connection failed: {exc}")


@router.post("/{repo_id}/monitoring")
def toggle_monitoring(repo_id: int, payload: MonitoringUpdate, db: Session = Depends(get_db)):
    """Enable or disable live continuous monitoring for a repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    repo.monitoring_enabled = payload.enabled
    db.commit()
    return {"id": repo.id, "monitoring_enabled": repo.monitoring_enabled}


@router.post("/{repo_id}/select-branch")
def select_branch(repo_id: int, payload: BranchSelect, db: Session = Depends(get_db)):
    """Select active branch for analysis."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    if repo.available_branches and payload.branch not in repo.available_branches:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Branch '{payload.branch}' not in available branches.")
    repo.selected_branch = payload.branch
    db.commit()
    return {"id": repo.id, "selected_branch": repo.selected_branch}


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
