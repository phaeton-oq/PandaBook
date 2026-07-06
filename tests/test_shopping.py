from datetime import date, timedelta

from app.api.routes_diet import _smart_shopping_fallback
from app.core.diet_engine import generate_day_plan
from app.core.nutrition import compute_targets
from app.db.converters import product_to_schema
from app.db.seed import CATALOG
from app.schemas import (
    ActivityLevel,
    DietaryPrefs,
    FridgeItem,
    Goal,
    Product,
    Sex,
    UserProfile,
)


def _catalog() -> list[Product]:
    out: list[Product] = []
    for name, cat, kcal, p, f, c, tags in CATALOG:
        out.append(Product(
            name=name, category=cat, kcal_100=kcal,
            protein_100=p, fat_100=f, carbs_100=c, tags=tags,
        ))
    return out


def _profile() -> UserProfile:
    return UserProfile(
        sex=Sex.male, age=25, weight_kg=78, height_cm=182,
        activity=ActivityLevel.moderate, goal=Goal.lose, prefs=DietaryPrefs(),
    )


def test_smart_fallback_for_pasta_skips_carb_fillers():
    catalog = _catalog()
    by_name = {p.name: p for p in catalog}
    fridge = [
        FridgeItem(product=by_name["Макароны"], quantity_g=500, expiry_date=date.today() + timedelta(days=30)),
        FridgeItem(product=by_name["Мёд"], quantity_g=200, expiry_date=date.today() + timedelta(days=60)),
    ]
    profile = _profile()
    targets = compute_targets(profile)
    plan = generate_day_plan(fridge, targets, profile.prefs)
    recs = _smart_shopping_fallback(catalog, fridge, targets, plan, profile.prefs)

    names = {_norm(rec.product_name) for rec in recs}
    assert "мёд" not in names
    assert "оливковое масло" not in names or "сыр" in " ".join(names)
    assert any("макарон" in rec.reason or "гарнир" in rec.reason or "овощ" in rec.reason for rec in recs)


def _norm(name: str) -> str:
    return name.strip().lower()


def test_grain_fridges_do_not_recommend_carb_fillers():
    catalog = _catalog()
    by_name = {p.name: p for p in catalog}
    profile = _profile()
    targets = compute_targets(profile)

    for grain_name in ("Макароны", "Рис белый", "Овсянка"):
        fridge = [
            FridgeItem(product=by_name[grain_name], quantity_g=400, expiry_date=date.today() + timedelta(days=30)),
        ]
        plan = generate_day_plan(fridge, targets, profile.prefs)
        recs = _smart_shopping_fallback(catalog, fridge, targets, plan, profile.prefs)
        names = {_norm(r.product_name) for r in recs}
        assert "мёд" not in names
        assert not names & {"рис белый", "овсянка", "макароны", "гречка"}
