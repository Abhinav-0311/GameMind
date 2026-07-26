"""Acceptance coverage for the private-beta owner, collaborator, and runtime workflow."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from main import app


@pytest.fixture
def auth_required():
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.AUTH_REQUIRED = original


@pytest.mark.integration
def test_private_beta_workspace_journey(monkeypatch, auth_required):
    """A team can move one source from upload to a role-safe runtime bundle."""
    import app.api.v1.projects as projects_module

    delivered_invites: list[str] = []
    monkeypatch.setattr(
        projects_module,
        "send_account_link",
        lambda _email, _subject, _path, token: delivered_invites.append(token),
    )

    owner = TestClient(app)
    editor = TestClient(app)
    viewer = TestClient(app)
    password = "correct-horse-battery-staple"
    suffix = uuid.uuid4().hex[:10]
    owner_email = f"owner-{suffix}@example.com"
    editor_email = f"editor-{suffix}@example.com"
    viewer_email = f"viewer-{suffix}@example.com"

    assert owner.post("/api/v1/auth/register", json={"email": owner_email, "password": password}).status_code == 201
    workspace_response = owner.post("/api/v1/projects/", json={"name": f"CyberRakshak beta {suffix}"})
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    headers = {"X-Game-Project-ID": workspace["id"]}

    gdd = b"""# CyberRakshak
    CyberRakshak is a story-driven ethical-hacking game. The player investigates a breach at a student innovation lab.
    ## Narrative
    Mentor Aanya guides the player through evidence gathering while the antagonist, GhostWire, manipulates public systems.
    ## NPC profiles
    NPC Aanya: Patient incident-response mentor who explains evidence clearly and challenges reckless decisions.
    NPC GhostWire: Calculating social engineer who speaks in controlled threats and misleading technical clues.
    ## Gameplay
    Players inspect terminals, correlate evidence, and choose whether to report or contain a compromised service.
    ## Levels
    The first level is the innovation lab. The second is a simulated city network with escalating incident response.
    ## Quest
    Quest 1: Objective: Restore the campus network by finding the compromised relay and preserving the evidence chain. Reward: Unlock the forensic analyst badge.
    ## Art direction
    Clean cyber-noir interfaces, restrained neon cyan, and readable high-contrast mission spaces.
    """
    upload = owner.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("cyberrakshak-gdd.txt", gdd, "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    blueprint = owner.post("/api/v1/blueprints/generate", headers=headers, json={"document_id": document_id})
    assert blueprint.status_code == 201, blueprint.text
    blueprint_id = blueprint.json()["id"]

    approval = owner.put(f"/api/v1/blueprints/{blueprint_id}/approve", headers=headers)
    assert approval.status_code == 200, approval.text
    materialized = owner.post(
        f"/api/v1/blueprints/{blueprint_id}/materialize",
        headers=headers,
        json={"confirm_incomplete": True},
    )
    assert materialized.status_code == 200, materialized.text
    assert owner.get(f"/api/v1/blueprints/{blueprint_id}/runtime-bundle", headers=headers).status_code == 200

    for email, role in ((editor_email, "editor"), (viewer_email, "viewer")):
        response = owner.post(
            f"/api/v1/projects/{workspace['id']}/invitations",
            json={"email": email, "role": role},
        )
        assert response.status_code == 202

    assert editor.post("/api/v1/auth/register", json={"email": editor_email, "password": password}).status_code == 201
    assert viewer.post("/api/v1/auth/register", json={"email": viewer_email, "password": password}).status_code == 201
    assert editor.post("/api/v1/projects/invitations/accept", json={"token": delivered_invites.pop(0)}).status_code == 200
    assert viewer.post("/api/v1/projects/invitations/accept", json={"token": delivered_invites.pop(0)}).status_code == 200

    editor_upload = editor.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("editor-note.txt", b"The breach starts in the lab relay room.", "text/plain")},
    )
    assert editor_upload.status_code == 201, editor_upload.text

    viewer_read = viewer.get(f"/api/v1/blueprints/{blueprint_id}", headers=headers)
    assert viewer_read.status_code == 200
    viewer_write = viewer.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("viewer-note.txt", b"This must not be written.", "text/plain")},
    )
    assert viewer_write.status_code == 403

    roster = owner.get(f"/api/v1/projects/{workspace['id']}/members")
    assert roster.status_code == 200
    assert {(member["email"], member["role"]) for member in roster.json()} == {
        (owner_email, "owner"),
        (editor_email, "editor"),
        (viewer_email, "viewer"),
    }
