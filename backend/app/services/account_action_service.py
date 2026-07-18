from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.user import AccountActionToken
from app.security import create_opaque_token, hash_opaque_token


class AccountActionService:
    @staticmethod
    def issue(db: Session, purpose: str, email: str, *, user_id=None, game_project_id=None, role=None, lifetime_minutes: int = 60) -> str:
        raw_token = create_opaque_token()
        db.add(AccountActionToken(
            token_hash=hash_opaque_token(raw_token), purpose=purpose, email=email.lower(),
            user_id=user_id, game_project_id=game_project_id, role=role,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=lifetime_minutes),
        ))
        db.commit()
        return raw_token

    @staticmethod
    def consume(db: Session, token: str, purpose: str, email: str | None = None) -> AccountActionToken | None:
        query = db.query(AccountActionToken).filter(
            AccountActionToken.token_hash == hash_opaque_token(token),
            AccountActionToken.purpose == purpose,
            AccountActionToken.consumed_at.is_(None),
        )
        if email is not None:
            query = query.filter(AccountActionToken.email == email.lower())
        record = query.first()
        if record is None or record.expires_at <= datetime.now(timezone.utc):
            return None
        record.consumed_at = datetime.now(timezone.utc)
        db.commit()
        return record
