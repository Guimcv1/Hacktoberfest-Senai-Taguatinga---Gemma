from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.models import RevokedToken, User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Token inválido ou expirado.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Autenticação obrigatória.")
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError:
        raise _unauthorized() from None

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if payload.get("type") != "access" or not jti or not user_id:
        raise _unauthorized()

    if db.get(RevokedToken, jti) is not None:
        raise _unauthorized("Sessão encerrada. Entre novamente.")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
