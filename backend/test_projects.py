from fastapi.testclient import TestClient
import uuid

from main import app


client = TestClient(app)


def test_projects_create_and_list():
    name = f"Moonlit Citadel {uuid.uuid4().hex[:8]}"
    created = client.post("/api/v1/projects/", json={"name": name})

    assert created.status_code == 201
    assert created.json()["id"].startswith("moonlit-citadel-")

    listed = client.get("/api/v1/projects/")
    assert listed.status_code == 200
    assert any(project["id"] == created.json()["id"] for project in listed.json())


def test_project_name_collision_is_rejected():
    name = f"Collision Test {uuid.uuid4().hex[:8]}"
    first = client.post("/api/v1/projects/", json={"name": name})
    duplicate = client.post("/api/v1/projects/", json={"name": name.lower().replace(" ", "-")})

    assert first.status_code == 201
    assert duplicate.status_code == 409
