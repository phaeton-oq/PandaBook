"""Auth + user profile — OWNER: Backend-2.

  POST /api/auth/register   create user (email, password, name, profile)
  POST /api/auth/login       verify password, issue JWT
  GET  /api/auth/me          current user + profile (feeds compute_targets)
Profile fields map 1:1 to schemas.UserProfile; store dietary prefs in
models.User.prefs_csv (see app.db.converters.parse_prefs).

Queries use SQLAlchemy ORM (parameterized) — no raw SQL, SQL-injection safe.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_utils import create_token, get_current_user
from app.api.password_utils import hash_password, verify_password
from app.db import models
from app.db.converters import parse_prefs
from app.db.session import get_db
from app.schemas import ActivityLevel, DietaryPrefs, Goal, Sex, UserProfile

router = APIRouter(prefix="/api/auth", tags=["auth"])

_AUTH_FAIL = "Invalid email or password"


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) < 3 or len(email) > 254 or "@" not in email:
        raise ValueError("Invalid email")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise ValueError("Invalid email")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=100)
    profile: UserProfile

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    email: str
    name: str
    profile: UserProfile


def _prefs_to_csv(prefs: DietaryPrefs) -> str:
    flags: list[str] = []
    if prefs.vegan:
        flags.append("vegan")
    if prefs.vegetarian:
        flags.append("vegetarian")
    if prefs.halal:
        flags.append("halal")
    if prefs.gluten_free:
        flags.append("gluten_free")
    if prefs.lactose_free:
        flags.append("lactose_free")
    flags.extend(prefs.allergens)
    return ",".join(flags)


def _user_to_profile(user: models.User) -> UserProfile:
    return UserProfile(
        sex=Sex(user.sex),
        age=user.age,
        weight_kg=user.weight_kg,
        height_cm=user.height_cm,
        activity=ActivityLevel(user.activity),
        goal=Goal(user.goal),
        prefs=parse_prefs(user.prefs_csv),
    )


def _apply_profile(user: models.User, profile: UserProfile) -> None:
    user.sex = profile.sex.value
    user.age = profile.age
    user.weight_kg = profile.weight_kg
    user.height_cm = profile.height_cm
    user.activity = profile.activity.value
    user.goal = profile.goal.value
    user.prefs_csv = _prefs_to_csv(profile.prefs)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.scalar(select(models.User).where(models.User.email == req.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = models.User(
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
    )
    _apply_profile(user, req.profile)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(models.User).where(models.User.email == req.email))
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _AUTH_FAIL)
    return TokenResponse(access_token=create_token(user.id))


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[models.User, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, name=user.name, profile=_user_to_profile(user))


class UpdateMeRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    profile: UserProfile | None = None


@router.patch("/me", response_model=MeResponse)
def update_me(
    req: UpdateMeRequest,
    user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> MeResponse:
    if req.name is not None:
        user.name = req.name
    if req.profile is not None:
        _apply_profile(user, req.profile)
    db.commit()
    db.refresh(user)
    return MeResponse(id=user.id, email=user.email, name=user.name, profile=_user_to_profile(user))
