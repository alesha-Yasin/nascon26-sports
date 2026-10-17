"""JWT auth utilities."""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from app.core.config import settings


def create_token(payload: dict, expires_hours: int = None) -> str:
    expires = expires_hours or settings.JWT_EXPIRE_HOURS
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(hours=expires)
    data["iat"] = datetime.utcnow()
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT. Raises JWTError on invalid/expired/tampered."""
    # Reject alg:none explicitly
    header = jwt.get_unverified_header(token)
    if header.get("alg", "").lower() == "none":
        raise JWTError("alg:none not allowed")
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return payload
