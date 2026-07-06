"""Daily ration generator.

Greedy allocator that builds breakfast/lunch/dinner/snack from what's in the
fridge, prioritizing products that expire soonest (anti food-waste) and
respecting the user's dietary preferences.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.filters import is_allowed
from app.schemas import (
    DayPlan,
    DietaryPrefs,
    FridgeItem,
    Meal,
    MealItem,
    MealType,
    Targets,
)

_MEAL_SPLIT: dict[MealType, float] = {
    MealType.breakfast: 0.25,
    MealType.lunch: 0.35,
    MealType.dinner: 0.30,
    MealType.snack: 0.10,
}

MIN_PORTION_G = 20
MAX_PORTION_G = 300
_EXPIRING_SOON_DAYS = 3


def _macros(item: FridgeItem, grams: float) -> tuple[float, float, float, float]:
    f = grams / 100
    p = item.product
    return p.kcal_100 * f, p.protein_100 * f, p.fat_100 * f, p.carbs_100 * f


def _sort_key(item: FridgeItem, day: date):
    # soonest expiry first; items without a date go last
    return item.expiry_date or date.max


def generate_day_plan(
    fridge: list[FridgeItem],
    targets: Targets,
    prefs: DietaryPrefs,
    day: date | None = None,
) -> DayPlan:
    day = day or date.today()
    soon = day + timedelta(days=_EXPIRING_SOON_DAYS)

    pool = sorted(
        (f for f in fridge if is_allowed(f.product, prefs) and f.product.kcal_100 > 0),
        key=lambda f: _sort_key(f, day),
    )
    remaining = [f.quantity_g for f in pool]

    meals: list[Meal] = []
    for meal_type, share in _MEAL_SPLIT.items():
        budget = targets.kcal * share
        meal = Meal(type=meal_type)
        acc_kcal = 0.0

        for i, item in enumerate(pool):
            if remaining[i] < MIN_PORTION_G or acc_kcal >= budget * 0.95:
                continue
            kcal_per_g = item.product.kcal_100 / 100
            grams = (budget - acc_kcal) / kcal_per_g
            grams = min(grams, remaining[i], MAX_PORTION_G)
            grams = round(grams / 10) * 10
            if grams < MIN_PORTION_G:
                continue

            kcal, p, f, c = _macros(item, grams)
            meal.items.append(MealItem(
                product_name=item.product.name, grams=grams,
                kcal=round(kcal), protein=round(p, 1), fat=round(f, 1), carbs=round(c, 1),
                expiring_soon=item.expiry_date is not None and item.expiry_date <= soon,
            ))
            meal.kcal += kcal
            meal.protein += p
            meal.fat += f
            meal.carbs += c
            remaining[i] -= grams
            acc_kcal += kcal

        for attr in ("kcal", "protein", "fat", "carbs"):
            setattr(meal, attr, round(getattr(meal, attr), 1))
        meals.append(meal)

    totals = Targets(
        kcal=round(sum(m.kcal for m in meals)),
        protein_g=round(sum(m.protein for m in meals)),
        fat_g=round(sum(m.fat for m in meals)),
        carbs_g=round(sum(m.carbs for m in meals)),
    )
    coverage = round(min(totals.kcal / targets.kcal, 1.0) * 100, 1) if targets.kcal else 0.0

    notes: list[str] = []
    if any(it.expiring_soon for m in meals for it in m.items):
        notes.append("В рацион включены продукты с истекающим сроком годности.")
    if coverage < 90:
        notes.append("Холодильника не хватает на дневную норму — смотри список докупок.")

    return DayPlan(day=day, targets=targets, meals=meals, totals=totals,
                   coverage_pct=coverage, notes=notes)
