"""Diet endpoints — the demo surface of the core engine (Backend-1).

POST /api/diet/plan : full flow — profile + fridge -> targets, day plan, shopping list.
GET  /api/diet/demo : canned example off the seed catalog for instant demos.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.auth_utils import get_current_user
from app.core.diet_engine import generate_day_plan
from app.core.nutrition import compute_targets
from app.core.recommender import recommend
from app.db import models
from app.db.converters import fridge_to_schema, product_to_schema, user_to_profile
from app.db.session import get_db
from app.integrations.llm import explain_plan, suggest_recipe
from app.schemas import (
    ActivityLevel,
    DayPlan,
    DietaryPrefs,
    FridgeItem,
    Goal,
    Product,
    Recipe,
    Sex,
    ShoppingItem,
    Targets,
    UserProfile,
)

router = APIRouter(prefix="/api/diet", tags=["diet"])

Mode = Literal["fast", "thinking"]


class PlanRequest(BaseModel):
    profile: UserProfile
    fridge: list[FridgeItem]
    # "fast" = free algorithmic plan; "thinking" = Pro, LLM reasons harder
    mode: Mode = "fast"
    # optional free-text wish, honored only in thinking mode
    request: str | None = None


class PlanResponse(BaseModel):
    mode: Mode
    targets: Targets
    plan: DayPlan
    shopping_list: list[ShoppingItem]
    # populated only in thinking mode
    explanation: str | None = None
    recipe: Recipe | None = None


class RecipeRequest(BaseModel):
    ingredients: list[str]


def _catalog(db: Session) -> list[Product]:
    return [product_to_schema(p) for p in db.scalars(select(models.Product)).all()]


def _used_products(plan: DayPlan) -> list[str]:
    seen: list[str] = []
    for meal in plan.meals:
        for item in meal.items:
            if item.product_name not in seen:
                seen.append(item.product_name)
    return seen


def _plan_summary(profile: UserProfile, plan: DayPlan, user_request: str | None) -> str:
    t, tot = plan.targets, plan.totals
    lines = [
        f"Цель пользователя: {profile.goal.value}.",
        f"Норма на день: {t.kcal} ккал, Б {t.protein_g} / Ж {t.fat_g} / У {t.carbs_g} г.",
        f"Составлено из холодильника: {tot.kcal} ккал, Б {tot.protein_g} / Ж {tot.fat_g} / У {tot.carbs_g} г.",
        f"Покрытие нормы: {plan.coverage_pct}%.",
        "Продукты в рационе: " + ", ".join(_used_products(plan)) + ".",
    ]
    if user_request:
        lines.append(f"Пожелание пользователя: {user_request}")
    return " ".join(lines)


def _enrich_thinking(profile: UserProfile, plan: DayPlan, user_request: str | None):
    used = _used_products(plan)
    recipe = suggest_recipe(used) if used else None
    explanation = explain_plan(_plan_summary(profile, plan, user_request)) or None
    return explanation, recipe


@router.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest, db: Session = Depends(get_db)) -> PlanResponse:
    targets = compute_targets(req.profile)
    day_plan = generate_day_plan(req.fridge, targets, req.profile.prefs)
    shopping = recommend(_catalog(db), targets, day_plan.totals, req.profile.prefs)

    explanation = recipe = None
    if req.mode == "thinking":
        explanation, recipe = _enrich_thinking(req.profile, day_plan, req.request)

    return PlanResponse(mode=req.mode, targets=targets, plan=day_plan,
                        shopping_list=shopping, explanation=explanation, recipe=recipe)


@router.get("/plan/me", response_model=PlanResponse)
def plan_me(
    mode: Mode = "fast",
    request: str | None = None,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Build the plan straight from the logged-in user's saved fridge + profile."""
    profile = user_to_profile(user)
    rows = db.scalars(
        select(models.FridgeItem)
        .where(models.FridgeItem.user_id == user.id)
        .options(joinedload(models.FridgeItem.product))
    ).all()
    fridge = [fridge_to_schema(r) for r in rows]

    targets = compute_targets(profile)
    day_plan = generate_day_plan(fridge, targets, profile.prefs)
    shopping = recommend(_catalog(db), targets, day_plan.totals, profile.prefs)

    explanation = recipe = None
    if mode == "thinking":
        explanation, recipe = _enrich_thinking(profile, day_plan, request)

    return PlanResponse(mode=mode, targets=targets, plan=day_plan,
                        shopping_list=shopping, explanation=explanation, recipe=recipe)


@router.post("/recipe", response_model=Recipe)
def recipe(req: RecipeRequest) -> Recipe:
    return suggest_recipe(req.ingredients)


@router.get("/demo", response_model=PlanResponse)
def demo(db: Session = Depends(get_db)) -> PlanResponse:
    catalog = _catalog(db)
    by_name = {p.name: p for p in catalog}
    picks = [("Куриная грудка", 300, 2), ("Овсянка", 200, 20),
             ("Яйцо куриное", 300, 5), ("Брокколи", 250, 4), ("Рис белый", 200, 30)]
    fridge = [
        FridgeItem(product=by_name[n], quantity_g=q,
                   expiry_date=date.today() + timedelta(days=d))
        for n, q, d in picks if n in by_name
    ]
    profile = UserProfile(
        sex=Sex.male, age=25, weight_kg=78, height_cm=182,
        activity=ActivityLevel.moderate, goal=Goal.lose, prefs=DietaryPrefs(),
    )
    targets = compute_targets(profile)
    day_plan = generate_day_plan(fridge, targets, profile.prefs)
    shopping = recommend(catalog, targets, day_plan.totals, profile.prefs)
    return PlanResponse(mode="fast", targets=targets, plan=day_plan, shopping_list=shopping)
