import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import GameProject
from app.models.user import ProjectMembership, User
from app.schemas import GameProjectCreate, GameProjectResponse, WorkspaceInvitationAccept, WorkspaceInvitationCreate, WorkspaceMemberResponse
from app.services.account_action_service import AccountActionService
from app.services.email_delivery_service import send_account_link


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
def list_projects(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """List named dashboard workspaces, oldest first for a stable default."""
    ensure_default_project(db)
    if current_user is None:
        return db.query(GameProject).order_by(GameProject.created_at.asc()).all()
    return (
        db.query(GameProject)
        .join(ProjectMembership, ProjectMembership.game_project_id == GameProject.id)
        .filter(ProjectMembership.user_id == current_user.id)
        .order_by(GameProject.created_at.asc())
        .all()
    )


@router.post("/", response_model=GameProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: GameProjectCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Create an empty workspace without modifying any existing project data."""
    project_id = _slugify(payload.name)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use at least one letter or number in the project name.")

    if db.get(GameProject, project_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A workspace with this name already exists.")

    project = GameProject(id=project_id, name=payload.name.strip())
    db.add(project)
    if current_user is not None:
        db.add(ProjectMembership(user_id=current_user.id, game_project_id=project.id, role="owner"))
    db.commit()
    db.refresh(project)
    return project


def _require_owner(db: Session, project_id: str, current_user: User | None) -> None:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required.")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.game_project_id == project_id,
    ).first()
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workspace owners can manage invitations.")


def _require_membership(db: Session, project_id: str, current_user: User | None) -> None:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required.")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.game_project_id == project_id,
    ).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this workspace.")


@router.get("/{project_id}/members", response_model=list[WorkspaceMemberResponse])
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if db.get(GameProject, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    _require_membership(db, project_id, current_user)
    memberships = (
        db.query(ProjectMembership)
        .join(User, ProjectMembership.user_id == User.id)
        .filter(ProjectMembership.game_project_id == project_id)
        .order_by(ProjectMembership.created_at.asc())
        .all()
    )
    return [
        WorkspaceMemberResponse(id=membership.user.id, email=membership.user.email, role=membership.role, joined_at=membership.created_at)
        for membership in memberships
    ]


@router.post("/{project_id}/invitations", status_code=status.HTTP_202_ACCEPTED)
def invite_to_project(
    project_id: str,
    payload: WorkspaceInvitationCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if db.get(GameProject, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    _require_owner(db, project_id, current_user)
    token = AccountActionService.issue(
        db, "workspace_invitation", payload.email, game_project_id=project_id, role=payload.role, lifetime_minutes=7 * 24 * 60,
    )
    send_account_link(payload.email, "Join a GameMind workspace", "/accept-invitation", token)
    return {"message": "Invitation created."}


@router.post("/invitations/accept", response_model=GameProjectResponse)
def accept_invitation(
    payload: WorkspaceInvitationAccept,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required.")
    record = AccountActionService.consume(db, payload.token, "workspace_invitation", email=current_user.email)
    if record is None or record.game_project_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid, expired, or belongs to another account.")
    project = db.get(GameProject, record.game_project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation is invalid or expired.")
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == current_user.id, ProjectMembership.game_project_id == project.id,
    ).first()
    if membership is None:
        db.add(ProjectMembership(user_id=current_user.id, game_project_id=project.id, role=record.role or "viewer"))
        db.commit()
    return project
