"""Assign unowned legacy workspaces to a registered administrator.

Run once after enabling authentication on an existing installation. It never
overwrites a workspace that already has a membership.
"""
from app.config import settings
from app.database import SessionLocal
from app.models.project import GameProject
from app.models.user import ProjectMembership, User


def main() -> None:
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    if not email:
        raise RuntimeError("Set BOOTSTRAP_ADMIN_EMAIL to the registered owner account.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise RuntimeError("No registered user exists for BOOTSTRAP_ADMIN_EMAIL.")

        unowned_projects = (
            db.query(GameProject)
            .outerjoin(ProjectMembership, ProjectMembership.game_project_id == GameProject.id)
            .filter(ProjectMembership.id.is_(None))
            .all()
        )
        for project in unowned_projects:
            db.add(ProjectMembership(user_id=user.id, game_project_id=project.id, role="owner"))
        db.commit()
        print(f"Assigned {len(unowned_projects)} unowned workspace(s) to {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
