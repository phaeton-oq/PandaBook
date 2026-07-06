"""Shopping-list recommender.

Compares the day's planned intake against targets and suggests catalog
products (respecting dietary prefs) to close the biggest macro gaps.
"""
from __future__ import annotations

from app.core.filters import is_allowed
from app.schemas import DietaryPrefs, Product, ShoppingItem, Targets

# minimum deficit (grams) worth recommending for
_MIN_DEFICIT_G = 15
_MAX_BUY_G = 400

_MACRO = {
    "protein": ("protein_100", "белка"),
    "fat": ("fat_100", "жиров"),
    "carbs": ("carbs_100", "углеводов"),
}
_TARGET_ATTR = {"protein": "protein_g", "fat": "fat_g", "carbs": "carbs_g"}


def _richest(catalog: list[Product], attr: str, prefs: DietaryPrefs) -> Product | None:
    allowed = [p for p in catalog if is_allowed(p, prefs)]
    if not allowed:
        return None
    return max(allowed, key=lambda p: getattr(p, attr))


def recommend(
    catalog: list[Product],
    targets: Targets,
    planned: Targets,
    prefs: DietaryPrefs,
) -> list[ShoppingItem]:
    recs: list[ShoppingItem] = []
    for macro, (attr, ru) in _MACRO.items():
        deficit = getattr(targets, _TARGET_ATTR[macro]) - getattr(planned, _TARGET_ATTR[macro])
        if deficit < _MIN_DEFICIT_G:
            continue
        product = _richest(catalog, attr, prefs)
        if product is None or getattr(product, attr) <= 0:
            continue
        grams = min(round(deficit / (getattr(product, attr) / 100) / 10) * 10, _MAX_BUY_G)
        if grams <= 0:
            continue
        recs.append(ShoppingItem(
            product_name=product.name,
            grams=grams,
            reason=f"покрывает нехватку {ru} (~{round(deficit)} г)",
        ))
    return recs
