"""Dietary-preference filtering, shared by the engine and recommender."""
from app.schemas import DietaryPrefs, Product

# tags that violate a given diet flag
_VEGAN_BLOCK = {"meat", "pork", "fish", "egg", "dairy", "honey"}
_VEGETARIAN_BLOCK = {"meat", "pork", "fish"}


def is_allowed(product: Product, prefs: DietaryPrefs) -> bool:
    tags = set(product.tags)
    if prefs.vegan and tags & _VEGAN_BLOCK:
        return False
    if prefs.vegetarian and tags & _VEGETARIAN_BLOCK:
        return False
    if prefs.halal and "pork" in tags:
        return False
    if prefs.gluten_free and "gluten" in tags:
        return False
    if prefs.lactose_free and "dairy" in tags:
        return False
    if tags & set(prefs.allergens):
        return False
    return True
