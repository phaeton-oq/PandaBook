"""Progress dashboard + panda gamification (Backend-1).

GET  /api/progress/dashboard : per-day КБЖУ, streak, panda mood.
POST /api/progress/log        : record eaten product (feeds the dashboard).

Uses a demo user by default (user_id=1) until auth lands (Backend-2).
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.nutrition import compute_targets
from app.core.progress import current_streak, daily_nutrition, panda_mood
from app.db import models
from app.db.converters import product_to_schema, user_to_profile
from app.db.session import get_db
from app.schemas import DayNutrition, Targets

router = APIRouter(prefix="/api/progress", tags=["progress"])


class DashboardResponse(BaseModel):
    targets: Targets
    days: list[DayNutrition]
    streak: int
    panda_emoji: str
    panda_label: str


class LogRequest(BaseModel):
    product_id: int
    grams: float
    meal_type: str = "mixed"
    day: date | None = None
    user_id: int = 1


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(user_id: int = 1, db: Session = Depends(get_db)) -> DashboardResponse:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")

    targets = compute_targets(user_to_profile(user))
    logs = db.scalars(
        select(models.ConsumptionLog).where(models.ConsumptionLog.user_id == user_id)
    ).all()
    products = {p.id: product_to_schema(p) for p in db.scalars(select(models.Product)).all()}
    entries = [(log.day, products[log.product_id], log.grams)
               for log in logs if log.product_id in products]

    days = daily_nutrition(entries, targets.kcal)
    streak = current_streak(days)
    today_met = bool(days) and days[-1].goal_met
    emoji, label = panda_mood(streak, today_met)
    return DashboardResponse(targets=targets, days=days, streak=streak,
                             panda_emoji=emoji, panda_label=label)


@router.post("/log")
def log(req: LogRequest, db: Session = Depends(get_db)) -> dict:
    if db.get(models.Product, req.product_id) is None:
        raise HTTPException(404, "product not found")
    db.add(models.ConsumptionLog(
        user_id=req.user_id, product_id=req.product_id,
        day=req.day or date.today(), meal_type=req.meal_type, grams=req.grams,
    ))
    db.commit()
    return {"ok": True}
