from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import utcnow
from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import Settings
from app.db.models import RevokedToken, User


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, *, email: str, password: str, name: str) -> User:
    normalized = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise AuthError("email_taken", "Este e-mail já está cadastrado.")
    user = User(
        id=str(uuid4()),
        email=normalized,
        password_hash=hash_password(password),
        name=name.strip(),
        created_at=utcnow(),
    )
    db.add(user)
    db.commit()
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


def revoke_token(db: Session, jti: str, expires_at) -> None:
    db.merge(RevokedToken(jti=jti, expires_at=expires_at))
    db.commit()
