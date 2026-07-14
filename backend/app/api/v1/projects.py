import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import GameProject
from app.schemas import GameProjectCreate, GameProjectResponse


router = APIRouter(prefix="/projects", tags=["projects"])

DEFAULT_PROJECT_ID = "default_project"
DEFAULT_PROJECT_NAME = "My first game"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80]


def ensure_default_project(db: Session) -> None:
    if db.get(GameProject, DEFAULT_PROJECT_ID) is None:
        db.add(GameProject(id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME))
        db.commit()


@router.get("/", response_model=list[GameProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List named dashboard workspaces, oldest first for a stable default."""
    ensure_default_project(db)
    return db.query(GameProject).order_by(GameProject.created_at.asc()).all()


@router.post("/", response_model=GameProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: GameProjectCreate, db: Session = Depends(get_db)):
    """Create an empty workspace without modifying any existing project data."""
    project_id = _slugify(payload.name)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use at least one letter or number in the project name.")

    if db.get(GameProject, project_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A workspace with this name already exists.")

    project = GameProject(id=project_id, name=payload.name.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
