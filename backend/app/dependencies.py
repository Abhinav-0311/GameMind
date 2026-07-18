from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import ProjectMembership, User
from app.security import SESSION_COOKIE_NAME, decode_access_token

session_cookie = APIKeyCookie(name=SESSION_COOKIE_NAME, auto_error=False)


def get_current_user(
    token: str | None = Depends(session_cookie),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve an authenticated user, or allow local demo mode to remain anonymous."""
    if not token:
        if settings.AUTH_REQUIRED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in is required.")
        return None

    try:
        user_id_raw, token_version = decode_access_token(token)
        user_id = UUID(user_id_raw)
    except (ValueError, jwt.PyJWTError):
        if not settings.AUTH_REQUIRED:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired.")

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.session_version != token_version:
        if not settings.AUTH_REQUIRED:
            return None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired.")
    return user


def get_game_project_id(
    request: Request,
    x_game_project_id: str = Header(default="default_project", alias="X-Game-Project-ID"),
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    """Accept a selected project only when the authenticated user has the required role."""
    if current_user is None:
        return x_game_project_id

    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.game_project_id == x_game_project_id,
    ).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this workspace.")

    if request.method not in {"GET", "HEAD", "OPTIONS"} and membership.role not in {"owner", "editor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This workspace is read-only for your account.")

    return x_game_project_id

def get_player_id(x_player_id: str = Header(default="default_player", alias="X-Player-ID")) -> str:
    return x_player_id
