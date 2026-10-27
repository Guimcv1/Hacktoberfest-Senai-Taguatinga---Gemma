from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import Settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, settings: Settings) -> tuple[str, str, datetime]:
    jti = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": user_id,
        "jti": jti,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
