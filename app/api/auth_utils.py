"""JWT helpers for Backend-2 auth (stdlib only, no extra deps)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)
_TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(user_id: int) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps(
        {"sub": str(user_id), "exp": int(time.time()) + _TOKEN_TTL},
        separators=(",", ":"),
    ).encode())
    sig = _b64url(hmac.new(
        settings.SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256,
    ).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> int:
    try:
        header, payload, sig = token.split(".")
        expected = _b64url(hmac.new(
            settings.SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256,
        ).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < time.time():
            raise ValueError("expired")
        return int(data["sub"])
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from e


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> models.User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(models.User, decode_token(creds.credentials))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
