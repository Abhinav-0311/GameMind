from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import GameProject
from app.models.user import ProjectMembership, User
from app.schemas import (
    AuthLoginRequest, AuthRegisterRequest, AuthSessionResponse, AuthUserResponse,
    EmailRequest, PasswordResetConfirmationRequest, TokenConfirmationRequest,
)
from app.security import SESSION_COOKIE_NAME, create_access_token, hash_password, verify_password
from app.services.auth_rate_limiter import auth_rate_limiter
from app.services.account_action_service import AccountActionService
from app.services.email_delivery_service import send_account_link

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_access_token(str(user.id), user.session_version),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _claim_legacy_workspace_if_unowned(db: Session, user: User) -> None:
    """Assign the legacy demo workspace to the first registered account only."""
    project = db.get(GameProject, "default_project")
    if project is None:
        return
    has_members = db.query(ProjectMembership).filter(ProjectMembership.game_project_id == project.id).first()
    if has_members is None:
        db.add(ProjectMembership(user_id=user.id, game_project_id=project.id, role="owner"))


def _rate_limit_key(request: Request, action: str, email: str | None = None) -> str:
    client_host = request.client.host if request.client else "unknown"
    normalized_email = email.strip().lower() if email else ""
    return f"{action}:{client_host}:{normalized_email}"


def _enforce_rate_limit(request: Request, action: str, email: str | None = None) -> str:
    key = _rate_limit_key(request, action, email)
    if not settings.auth_rate_limit_enabled:
        return key

    result = auth_rate_limiter.check(
        key,
        settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
    return key


@router.post("/register", response_model=AuthUserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit_key = _enforce_rate_limit(request, "register")
    if settings.auth_rate_limit_enabled:
        auth_rate_limiter.record(rate_limit_key, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS)
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account already exists for this email.")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    _claim_legacy_workspace_if_unowned(db, user)
    db.commit()
    db.refresh(user)
    verification_token = AccountActionService.issue(db, "email_verification", user.email, user_id=user.id, lifetime_minutes=24 * 60)
    send_account_link(user.email, "Verify your GameMind email", "/verify-email", verification_token)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=AuthUserResponse)
def login(payload: AuthLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit_key = _enforce_rate_limit(request, "login", payload.email)
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if settings.auth_rate_limit_enabled:
            auth_rate_limiter.record(rate_limit_key, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if settings.require_email_verification and not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verify your email before signing in.")

    auth_rate_limiter.clear(rate_limit_key)
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.get("/session", response_model=AuthSessionResponse)
def session(current_user: User | None = Depends(get_current_user)):
    return AuthSessionResponse(auth_required=settings.AUTH_REQUIRED, user=current_user)


@router.post("/email-verification/request", status_code=status.HTTP_202_ACCEPTED)
def request_email_verification(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_rate_limit(request, "verify-email", payload.email)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is not None and user.is_active and not user.email_verified:
        token = AccountActionService.issue(db, "email_verification", user.email, user_id=user.id, lifetime_minutes=24 * 60)
        send_account_link(user.email, "Verify your GameMind email", "/verify-email", token)
    return {"message": "If an account needs verification, a link has been sent."}


@router.post("/email-verification/confirm", response_model=AuthUserResponse)
def confirm_email_verification(payload: TokenConfirmationRequest, db: Session = Depends(get_db)):
    record = AccountActionService.consume(db, payload.token, "email_verification")
    if record is None or record.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid or expired.")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid or expired.")
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_rate_limit(request, "password-reset", payload.email)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is not None and user.is_active:
        token = AccountActionService.issue(db, "password_reset", user.email, user_id=user.id, lifetime_minutes=60)
        send_account_link(user.email, "Reset your GameMind password", "/reset-password", token)
    return {"message": "If an account exists, a password reset link has been sent."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(payload: PasswordResetConfirmationRequest, db: Session = Depends(get_db)):
    record = AccountActionService.consume(db, payload.token, "password_reset")
    if record is None or record.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or expired.")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or expired.")
    user.password_hash = hash_password(payload.password)
    user.session_version += 1
    db.commit()
