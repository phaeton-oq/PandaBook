"""Daily ration generator.

Builds breakfast/lunch/dinner/snack from what's in the fridge:
- prioritizes products that expire soonest (anti food-waste),
- respects dietary preferences,
- spreads variety: each product is dealt to a single meal (round-robin over
  expiry-sorted items), so meals differ and one product isn't smeared across
  the whole day,
- skips drinks/sweets so they don't become a meal's base.
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
    Product,
    Targets,
)

_MEAL_ORDER = [MealType.breakfast, MealType.lunch, MealType.dinner, MealType.snack]
_MEAL_SPLIT: dict[MealType, float] = {
    MealType.breakfast: 0.25,
    MealType.lunch: 0.35,
    MealType.dinner: 0.30,
    MealType.snack: 0.10,
}

MIN_PORTION_G = 20
MAX_PORTION_G = 300
_EXPIRING_SOON_DAYS = 3

# Heuristic: things that shouldn't be a meal's base. Matched as substrings of
# "name + category" (lowercase). Rough but cheap — tune the lists as needed.
_DRINK_WORDS = ("напит", "газиров", "тархун", "лимонад", "cola", "pepsi", "soda",
                "juice", "water", "квас", "морс", "сок", "чай", "кофе", "компот",
                "beverage", "drink", "вода")
_SWEET_WORDS = ("конфет", "шоколад", "chocolate", "батончик", "мармелад", "candy",
                "вафл", "wafer", "печенье", "пастил", "зефир")


def _is_edible(product: Product) -> bool:
    text = (product.name + " " + product.category).lower()
    return not any(w in text for w in _DRINK_WORDS + _SWEET_WORDS)


def _macros(product: Product, grams: float) -> tuple[float, float, float, float]:
    f = grams / 100
    return (product.kcal_100 * f, product.protein_100 * f,
            product.fat_100 * f, product.carbs_100 * f)


def generate_day_plan(
    fridge: list[FridgeItem],
    targets: Targets,
    prefs: DietaryPrefs,
    day: date | None = None,
) -> DayPlan:
    day = day or date.today()
    soon = day + timedelta(days=_EXPIRING_SOON_DAYS)

    pool = sorted(
        (f for f in fridge
         if is_allowed(f.product, prefs) and f.product.kcal_100 > 0 and _is_edible(f.product)),
        key=lambda f: f.expiry_date or date.max,
    )

    # deal each product to exactly one meal → variety, no cross-meal smearing
    assigned: dict[MealType, list[FridgeItem]] = {mt: [] for mt in _MEAL_ORDER}
    for idx, item in enumerate(pool):
        assigned[_MEAL_ORDER[idx % len(_MEAL_ORDER)]].append(item)

    meals: list[Meal] = []
    for meal_type in _MEAL_ORDER:
        budget = targets.kcal * _MEAL_SPLIT[meal_type]
        meal = Meal(type=meal_type)
        acc_kcal = 0.0

        for item in assigned[meal_type]:  # already expiry-sorted (stable)
            if acc_kcal >= budget * 0.95:
                break
            kcal_per_g = item.product.kcal_100 / 100
            grams = min((budget - acc_kcal) / kcal_per_g, item.quantity_g, MAX_PORTION_G)
            grams = round(grams / 10) * 10
            if grams < MIN_PORTION_G:
                continue

            kcal, p, f, c = _macros(item.product, grams)
            meal.items.append(MealItem(
                product_name=item.product.name, grams=grams,
                kcal=round(kcal), protein=round(p, 1), fat=round(f, 1), carbs=round(c, 1),
                expiring_soon=item.expiry_date is not None and item.expiry_date <= soon,
            ))
            meal.kcal += kcal
            meal.protein += p
            meal.fat += f
            meal.carbs += c
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
