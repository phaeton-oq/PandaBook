"""Auth + user profile — OWNER: Backend-2.

  POST /api/auth/register   create user (email, name, profile)
  POST /api/auth/login       issue session/JWT
  GET  /api/auth/me          current user + profile (feeds compute_targets)
Profile fields map 1:1 to schemas.UserProfile; store dietary prefs in
models.User.prefs_csv (see app.db.converters.parse_prefs).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_utils import create_token, get_current_user
from app.db import models
from app.db.converters import parse_prefs
from app.db.session import get_db
from app.schemas import ActivityLevel, DietaryPrefs, Goal, Sex, UserProfile

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    name: str = ""
    profile: UserProfile


class LoginRequest(BaseModel):
    email: str


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
    user = models.User(email=req.email, name=req.name)
    _apply_profile(user, req.profile)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(models.User).where(models.User.email == req.email))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown email")
    return TokenResponse(access_token=create_token(user.id))


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[models.User, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, name=user.name, profile=_user_to_profile(user))
