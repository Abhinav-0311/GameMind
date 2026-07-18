import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.user import User
from main import app


@pytest.fixture
def auth_required():
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.AUTH_REQUIRED = original


def test_email_verification_and_password_reset_revoke_existing_sessions(monkeypatch, auth_required):
    import app.api.v1.auth as auth_module

    delivered: list[str] = []
    monkeypatch.setattr(auth_module, "send_account_link", lambda _email, _subject, _path, token: delivered.append(token))
    client = TestClient(app)
    email = f"lifecycle-{uuid.uuid4().hex[:10]}@example.com"
    password = "correct-horse-battery-staple"

    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    verification_token = delivered.pop()
    assert client.post("/api/v1/auth/email-verification/confirm", json={"token": verification_token}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": password}).status_code == 200

    assert client.post("/api/v1/auth/password-reset/request", json={"email": email}).status_code == 202
    reset_token = delivered.pop()
    assert client.post("/api/v1/auth/password-reset/confirm", json={"token": reset_token, "password": "new-correct-horse-battery"}).status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "new-correct-horse-battery"}).status_code == 200


def test_owner_can_invite_matching_account_to_workspace(monkeypatch, auth_required):
    import app.api.v1.projects as projects_module

    delivered: list[str] = []
    monkeypatch.setattr(projects_module, "send_account_link", lambda _email, _subject, _path, token: delivered.append(token))
    owner_client = TestClient(app)
    invitee_client = TestClient(app)
    password = "correct-horse-battery-staple"
    owner_email = f"owner-{uuid.uuid4().hex[:10]}@example.com"
    invitee_email = f"invitee-{uuid.uuid4().hex[:10]}@example.com"

    assert owner_client.post("/api/v1/auth/register", json={"email": owner_email, "password": password}).status_code == 201
    workspace = owner_client.post("/api/v1/projects/", json={"name": f"Shared game {uuid.uuid4().hex[:6]}"})
    assert workspace.status_code == 201
    assert owner_client.post(f"/api/v1/projects/{workspace.json()['id']}/invitations", json={"email": invitee_email, "role": "editor"}).status_code == 202
    invitation_token = delivered.pop()

    assert invitee_client.post("/api/v1/auth/register", json={"email": invitee_email, "password": password}).status_code == 201
    accepted = invitee_client.post("/api/v1/projects/invitations/accept", json={"token": invitation_token})
    assert accepted.status_code == 200
    assert accepted.json()["id"] == workspace.json()["id"]
