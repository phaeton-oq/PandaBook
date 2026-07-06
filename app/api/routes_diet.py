"""Diet endpoints — the demo surface of the core engine (Backend-1).

POST /api/diet/plan : full flow — profile + fridge -> targets, day plan, shopping list.
GET  /api/diet/demo : canned example off the seed catalog for instant demos.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.auth_utils import get_current_user
from app.core.diet_engine import generate_day_plan
from app.core.filters import is_allowed
from app.core.nutrition import compute_targets
from app.core.recommender import recommend
from app.db import models
from app.db.converters import fridge_to_schema, product_to_schema, user_to_profile
from app.db.session import get_db
from app.integrations.llm import explain_plan, suggest_recipe, suggest_shopping_list
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
_SHOPPING_CACHE_TTL = 300  # seconds
_shopping_cache: dict[str, tuple[float, list[ShoppingItem]]] = {}


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


def _fridge_lines(fridge: list[FridgeItem]) -> str:
    if not fridge:
        return "Холодильник пуст."
    lines = []
    for item in fridge:
        exp = f", годен до {item.expiry_date}" if item.expiry_date else ""
        lines.append(f"- {item.product.name}: {item.quantity_g} г{exp}")
    return "\n".join(lines)


def _shopping_context(
    profile: UserProfile,
    fridge: list[FridgeItem],
    targets: Targets,
    plan: DayPlan,
) -> str:
    t, tot = targets, plan.totals
    prefs = profile.prefs
    flags = [k for k, v in [
        ("веган", prefs.vegan), ("вегетарианец", prefs.vegetarian),
        ("халяль", prefs.halal), ("без глютена", prefs.gluten_free),
        ("без лактозы", prefs.lactose_free),
    ] if v]
    d_protein = round(t.protein_g - tot.protein_g)
    d_fat = round(t.fat_g - tot.fat_g)
    d_carbs = round(t.carbs_g - tot.carbs_g)
    grain_note = (
        "Дома уже есть гарнир/углеводы (макароны, каша, рис и т.п.) — "
        "НЕ предлагай докупать углеводы; предложи белок, овощи и жиры к тому, что уже есть.\n"
        if _fridge_has_grains(fridge) else ""
    )
    return (
        f"Цель: {profile.goal.value}. Активность: {profile.activity.value}.\n"
        f"Ограничения: {', '.join(flags) if flags else 'нет'}; "
        f"аллергены-исключения: {', '.join(prefs.allergens) if prefs.allergens else 'нет'}.\n\n"
        f"Норма на день: {round(t.kcal)} ккал, Б {round(t.protein_g)} / "
        f"Ж {round(t.fat_g)} / У {round(t.carbs_g)} г.\n"
        f"Из холодильника набрано: {round(tot.kcal)} ккал, Б {round(tot.protein_g)} / "
        f"Ж {round(tot.fat_g)} / У {round(tot.carbs_g)} г.\n"
        f"Покрытие нормы: {plan.coverage_pct}%.\n"
        f"Дефицит: белок {d_protein} г, жиры {d_fat} г, углеводы {d_carbs} г.\n"
        f"{grain_note}"
        f"Продукты в рационе на сегодня: {', '.join(_used_products(plan)) or 'нет'}.\n\n"
        f"УЖЕ ЕСТЬ В ХОЛОДИЛЬНИКЕ (эти продукты НЕЛЬЗЯ добавлять в список докупок):\n"
        f"{_fridge_lines(fridge)}\n\n"
        f"Составь список докупок под ЭТО содержимое холодильника, а не универсальный шаблон."
    )


def _norm_name(name: str) -> str:
    return name.strip().lower()


def _fridge_name_set(fridge: list[FridgeItem]) -> set[str]:
    return {_norm_name(item.product.name) for item in fridge}


def _catalog_without_fridge(catalog: list[Product], fridge: list[FridgeItem]) -> list[Product]:
    in_fridge = _fridge_name_set(fridge)
    return [p for p in catalog if _norm_name(p.name) not in in_fridge]


def _filter_fridge_duplicates(items: list[ShoppingItem], fridge: list[FridgeItem]) -> list[ShoppingItem]:
    in_fridge = _fridge_name_set(fridge)
    return [s for s in items if _norm_name(s.product_name) not in in_fridge]


_GRAIN_HINTS = ("макар", "рис", "овсян", "греч", "хлеб", "grain", "паст")
_CARB_FILLERS = ("мёд", "мед", "сахар", "рис", "овсян", "греч", "макар", "хлеб", "банан")
_MIN_DEFICIT_G = 15
_MAX_BUY_G = 400


def _fridge_has_grains(fridge: list[FridgeItem]) -> bool:
    for item in fridge:
        text = (item.product.name + " " + item.product.category).lower()
        if item.product.category == "grain" or any(h in text for h in _GRAIN_HINTS):
            return True
    return False


def _fridge_has_category(fridge: list[FridgeItem], category: str) -> bool:
    return any(item.product.category == category for item in fridge)


def _fridge_seed(fridge: list[FridgeItem]) -> str:
    return "|".join(sorted(_norm_name(item.product.name) for item in fridge))


def _products_by_name(catalog: list[Product]) -> dict[str, Product]:
    return {_norm_name(p.name): p for p in catalog}


def _pick_product(
    names: list[str],
    by_name: dict[str, Product],
    prefs: DietaryPrefs,
    seed: str,
) -> Product | None:
    allowed = [by_name[_norm_name(n)] for n in names if _norm_name(n) in by_name and is_allowed(by_name[_norm_name(n)], prefs)]
    if not allowed:
        return None
    return allowed[hash(seed) % len(allowed)]


def _grams_for_macro(product: Product, attr: str, deficit_g: float) -> int:
    per100 = getattr(product, attr)
    if per100 <= 0:
        return 0
    grams = min(round(deficit_g / (per100 / 100) / 10) * 10, _MAX_BUY_G)
    return max(grams, 0)


def _smart_shopping_fallback(
    catalog: list[Product],
    fridge: list[FridgeItem],
    targets: Targets,
    plan: DayPlan,
    prefs: DietaryPrefs,
) -> list[ShoppingItem]:
    """Context-aware offline list — complements what's already in the fridge."""
    available = _catalog_without_fridge(catalog, fridge)
    by_name = _products_by_name(available)
    if not by_name:
        return []

    t, tot = targets, plan.totals
    deficits = {
        "protein": t.protein_g - tot.protein_g,
        "fat": t.fat_g - tot.fat_g,
        "carbs": t.carbs_g - tot.carbs_g,
    }
    has_grain = _fridge_has_grains(fridge)
    seed = _fridge_seed(fridge)
    recs: list[ShoppingItem] = []

    if deficits["protein"] >= _MIN_DEFICIT_G:
        if has_grain:
            candidates = ["Яйцо куриное", "Тунец консерв.", "Творог 5%", "Куриная грудка", "Фасоль"]
            reason = "к имеющимся макаронам/гарниру не хватает белка"
        else:
            candidates = ["Куриная грудка", "Яйцо куриное", "Творог 5%", "Лосось", "Чечевица"]
            reason = f"закрывает нехватку белка (~{round(deficits['protein'])} г)"
        product = _pick_product(candidates, by_name, prefs, seed + ":p")
        if product:
            grams = _grams_for_macro(product, "protein_100", deficits["protein"])
            if grams > 0:
                recs.append(ShoppingItem(product_name=product.name, grams=grams, reason=reason))

    if deficits["fat"] >= _MIN_DEFICIT_G:
        if has_grain:
            candidates = ["Сыр твёрдый", "Авокадо", "Сливочное масло", "Йогурт натур."]
            reason = "добавит жиры к текущим продуктам"
        else:
            candidates = ["Авокадо", "Оливковое масло", "Сыр твёрдый", "Миндаль"]
            reason = f"закрывает нехватку жиров (~{round(deficits['fat'])} г)"
        product = _pick_product(candidates, by_name, prefs, seed + ":f")
        if product:
            grams = _grams_for_macro(product, "fat_100", deficits["fat"])
            if grams > 0:
                recs.append(ShoppingItem(product_name=product.name, grams=grams, reason=reason))

    if deficits["carbs"] >= _MIN_DEFICIT_G and not has_grain:
        candidates = ["Гречка", "Рис белый", "Картофель", "Овсянка"]
        product = _pick_product(candidates, by_name, prefs, seed + ":c")
        if product:
            grams = _grams_for_macro(product, "carbs_100", deficits["carbs"])
            if grams > 0:
                recs.append(ShoppingItem(
                    product_name=product.name,
                    grams=grams,
                    reason=f"закрывает нехватку углеводов (~{round(deficits['carbs'])} г)",
                ))

    if has_grain and not _fridge_has_category(fridge, "veg"):
        veg = _pick_product(["Брокколи", "Помидор", "Огурец", "Шпинат", "Морковь"], by_name, prefs, seed + ":v")
        if veg and not any(_norm_name(r.product_name) == _norm_name(veg.name) for r in recs):
            recs.append(ShoppingItem(
                product_name=veg.name,
                grams=250,
                reason="овощи к имеющимся макаронам/гарниру",
            ))

    return recs[:6]


def _drop_redundant_carbs(items: list[ShoppingItem], fridge: list[FridgeItem]) -> list[ShoppingItem]:
    if not _fridge_has_grains(fridge):
        return items
    out: list[ShoppingItem] = []
    for item in items:
        name = _norm_name(item.product_name)
        if any(h in name for h in _CARB_FILLERS):
            continue
        out.append(item)
    return out


def _shopping_cache_key(user_id: int, fridge: list[FridgeItem], mode: Mode) -> str:
    payload = "|".join(
        sorted(f"{_norm_name(item.product.name)}:{item.quantity_g}" for item in fridge)
    )
    return sha256(f"{user_id}:{mode}:{payload}".encode()).hexdigest()


def _cached_shopping(key: str) -> list[ShoppingItem] | None:
    hit = _shopping_cache.get(key)
    if not hit:
        return None
    ts, items = hit
    if time.time() - ts > _SHOPPING_CACHE_TTL:
        _shopping_cache.pop(key, None)
        return None
    return items


def _store_shopping_cache(key: str, items: list[ShoppingItem]) -> None:
    _shopping_cache[key] = (time.time(), items)


def _shopping_list(
    profile: UserProfile,
    fridge: list[FridgeItem],
    targets: Targets,
    plan: DayPlan,
    catalog: list[Product],
    *,
    mode: Mode = "fast",
    user_id: int | None = None,
) -> list[ShoppingItem]:
    fallback = _smart_shopping_fallback(catalog, fridge, targets, plan, profile.prefs)
    if mode != "thinking":
        return fallback or recommend(
            _catalog_without_fridge(catalog, fridge), targets, plan.totals, profile.prefs,
        )

    cache_key = _shopping_cache_key(user_id, fridge, mode) if user_id is not None else None
    if cache_key:
        cached = _cached_shopping(cache_key)
        if cached is not None:
            return cached

    llm = suggest_shopping_list(_shopping_context(profile, fridge, targets, plan))
    if llm is not None:
        cleaned = _drop_redundant_carbs(_filter_fridge_duplicates(llm, fridge), fridge)
        if cleaned:
            if cache_key:
                _store_shopping_cache(cache_key, cleaned)
            return cleaned

    result = fallback or recommend(
        _catalog_without_fridge(catalog, fridge), targets, plan.totals, profile.prefs,
    )
    if cache_key and result:
        _store_shopping_cache(cache_key, result)
    return result


@router.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest, db: Session = Depends(get_db)) -> PlanResponse:
    targets = compute_targets(req.profile)
    day_plan = generate_day_plan(req.fridge, targets, req.profile.prefs)
    shopping = _shopping_list(
        req.profile, req.fridge, targets, day_plan, _catalog(db), mode=req.mode,
    )

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
    shopping = _shopping_list(
        profile, fridge, targets, day_plan, _catalog(db),
        mode=mode, user_id=user.id,
    )

    explanation = recipe = None
    if mode == "thinking":
        explanation, recipe = _enrich_thinking(profile, day_plan, request)

    return PlanResponse(mode=mode, targets=targets, plan=day_plan,
                        shopping_list=shopping, explanation=explanation, recipe=recipe)


@router.get("/shopping/me", response_model=list[ShoppingItem])
def shopping_me(
    mode: Mode = "thinking",
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShoppingItem]:
    """Shopping list from the user's fridge; LLM in thinking mode, algorithm in fast."""
    profile = user_to_profile(user)
    rows = db.scalars(
        select(models.FridgeItem)
        .where(models.FridgeItem.user_id == user.id)
        .options(joinedload(models.FridgeItem.product))
    ).all()
    fridge = [fridge_to_schema(r) for r in rows]
    targets = compute_targets(profile)
    day_plan = generate_day_plan(fridge, targets, profile.prefs)
    return _shopping_list(
        profile, fridge, targets, day_plan, _catalog(db),
        mode=mode, user_id=user.id,
    )


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
