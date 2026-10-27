from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.deps import utcnow
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import RevokedToken, User


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _email_taken() -> AuthError:
    return AuthError("email_taken", "Este e-mail já está cadastrado.")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, *, email: str, password: str, name: str) -> User:
    normalized = normalize_email(email)
    if db.scalar(select(User.id).where(User.email == normalized)) is not None:
        raise _email_taken()
    user = User(
        id=str(uuid4()),
        email=normalized,
        password_hash=hash_password(password),
        name=name.strip(),
        created_at=utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Dois cadastros simultâneos com o mesmo e-mail: o índice único decide.
        db.rollback()
        raise _email_taken() from None
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials", "E-mail ou senha inválidos.")
    return user


def issue_token(user: User, settings: Settings) -> tuple[str, int]:
    token, _jti, _expires = create_access_token(user.id, settings)
    return token, settings.jwt_expires_minutes * 60


def purge_expired_revocations(db: Session) -> None:
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at <= utcnow()))
    db.commit()


def revoke_token(db: Session, jti: str, expires_at: datetime) -> None:
    db.merge(RevokedToken(jti=jti, expires_at=expires_at))
    db.commit()
    purge_expired_revocations(db)
