import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.dependencies import get_game_project_id
from app.models.project import GameProject
from app.models.user import ProjectMembership, User
from app.services.auth_rate_limiter import auth_rate_limiter
from app.security import hash_password
from main import app


@pytest.fixture
def auth_required():
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.AUTH_REQUIRED = original


def test_register_login_and_session_cookie(auth_required):
    client = TestClient(app)
    email = f"builder-{uuid.uuid4().hex[:10]}@example.com"

    created = client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery-staple"})
    assert created.status_code == 201
    assert created.json()["email"] == email
    assert "gamemind_session" in created.headers.get("set-cookie", "")
    assert "HttpOnly" in created.headers.get("set-cookie", "")

    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["email"] == email

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/session").status_code == 401

    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
    assert logged_in.status_code == 200


def test_project_membership_blocks_cross_project_access(auth_required):
    owner_client = TestClient(app)
    outsider_client = TestClient(app)
    owner_email = f"owner-{uuid.uuid4().hex[:10]}@example.com"
    outsider_email = f"outsider-{uuid.uuid4().hex[:10]}@example.com"
    password = "correct-horse-battery-staple"

    assert owner_client.post("/api/v1/auth/register", json={"email": owner_email, "password": password}).status_code == 201
    project = owner_client.post("/api/v1/projects/", json={"name": f"Owner workspace {uuid.uuid4().hex[:6]}"})
    assert project.status_code == 201

    assert outsider_client.post("/api/v1/auth/register", json={"email": outsider_email, "password": password}).status_code == 201
    denied = outsider_client.get("/api/v1/documents", headers={"X-Game-Project-ID": project.json()["id"]})
    assert denied.status_code == 403


def test_viewer_cannot_mutate_workspace(db_session, auth_required):
    owner = User(email=f"owner-{uuid.uuid4().hex[:10]}@example.com", password_hash="hash")
    viewer = User(email=f"viewer-{uuid.uuid4().hex[:10]}@example.com", password_hash="hash")
    project = GameProject(id=f"project-{uuid.uuid4().hex[:8]}", name="Read only")
    db_session.add_all([owner, viewer, project])
    db_session.flush()
    db_session.add(ProjectMembership(user_id=viewer.id, game_project_id=project.id, role="viewer"))
    db_session.commit()

    request = Request({"type": "http", "method": "POST", "path": "/api/v1/documents"})
    with pytest.raises(HTTPException) as error:
        get_game_project_id(request, project.id, viewer, db_session)
    assert error.value.status_code == 403


def test_login_rate_limit_returns_retry_after(db_session, auth_required):
    original_enabled = settings.AUTH_RATE_LIMIT_ENABLED
    original_max_attempts = settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS
    auth_rate_limiter.reset()
    settings.AUTH_RATE_LIMIT_ENABLED = True
    settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS = 2
    try:
        email = f"limited-{uuid.uuid4().hex[:10]}@example.com"
        user = User(email=email, password_hash=hash_password("correct-horse-battery-staple"))
        db_session.add(user)
        db_session.commit()
        client = TestClient(app)

        for _ in range(2):
            response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password-value"})
            assert response.status_code == 401

        blocked = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password-value"})
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
    finally:
        settings.AUTH_RATE_LIMIT_ENABLED = original_enabled
        settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS = original_max_attempts
        auth_rate_limiter.reset()
