"""Progress dashboard + panda gamification.

Aggregates consumption history into per-day КБЖУ, computes a "goal met" streak,
and maps it to the panda's mood. Pure functions — DB-free and testable.
"""
from __future__ import annotations

from datetime import date

from app.schemas import DayNutrition, Product

# a day counts as "on target" if calories land within this band of the goal
_GOAL_BAND = (0.85, 1.15)


def daily_nutrition(
    entries: list[tuple[date, Product, float]],
    target_kcal: float,
) -> list[DayNutrition]:
    """entries: (day, product, grams). Returns per-day totals sorted by day."""
    agg: dict[date, list[float]] = {}
    for day, product, grams in entries:
        f = grams / 100
        t = agg.setdefault(day, [0.0, 0.0, 0.0, 0.0])
        t[0] += product.kcal_100 * f
        t[1] += product.protein_100 * f
        t[2] += product.fat_100 * f
        t[3] += product.carbs_100 * f

    out: list[DayNutrition] = []
    for day in sorted(agg):
        kcal, p, fat, c = agg[day]
        met = bool(target_kcal) and _GOAL_BAND[0] * target_kcal <= kcal <= _GOAL_BAND[1] * target_kcal
        out.append(DayNutrition(day=day, kcal=round(kcal), protein_g=round(p),
                                fat_g=round(fat), carbs_g=round(c), goal_met=met))
    return out


def current_streak(days: list[DayNutrition]) -> int:
    """Consecutive on-target days counting back from the most recent day."""
    streak = 0
    for d in reversed(days):
        if not d.goal_met:
            break
        streak += 1
    return streak


def panda_mood(streak: int, today_met: bool) -> tuple[str, str]:
    """(emoji, label) for the mascot."""
    if streak >= 3:
        return "🐼✨", "Панда в восторге — так держать!"
    if today_met or streak >= 1:
        return "🐼", "Панда довольна"
    return "🐼💤", "Панду пора покормить по плану"
