from datetime import date, timedelta

from app.core.diet_engine import generate_day_plan
from app.core.nutrition import compute_targets
from app.core.recommender import recommend
from app.schemas import (
    ActivityLevel,
    DietaryPrefs,
    FridgeItem,
    Goal,
    Product,
    Sex,
    Targets,
    UserProfile,
)

CHICKEN = Product(name="Куриная грудка", kcal_100=165, protein_100=31, fat_100=3.6, carbs_100=0, tags=["meat"])
OATS = Product(name="Овсянка", kcal_100=366, protein_100=12, fat_100=6, carbs_100=62, tags=["gluten"])
PORK = Product(name="Свинина", kcal_100=242, protein_100=27, fat_100=14, carbs_100=0, tags=["meat", "pork"])
TOFU = Product(name="Тофу", kcal_100=76, protein_100=8, fat_100=4.8, carbs_100=1.9, tags=[])


def _profile(goal=Goal.maintain, prefs=None):
    return UserProfile(sex=Sex.male, age=25, weight_kg=75, height_cm=180,
                       activity=ActivityLevel.moderate, goal=goal,
                       prefs=prefs or DietaryPrefs())


def test_targets_scale_with_goal():
    lose = compute_targets(_profile(Goal.lose))
    gain = compute_targets(_profile(Goal.gain))
    assert lose.kcal < gain.kcal
    assert lose.protein_g > 0 and lose.fat_g > 0 and lose.carbs_g > 0


def test_plan_respects_fridge_quantities():
    fridge = [FridgeItem(product=CHICKEN, quantity_g=200)]
    targets = compute_targets(_profile())
    plan = generate_day_plan(fridge, targets, _profile().prefs)
    used = sum(it.grams for m in plan.meals for it in m.items if it.product_name == CHICKEN.name)
    assert used <= 200


def test_expiry_priority_flagged():
    soon = date.today() + timedelta(days=1)
    fridge = [
        FridgeItem(product=OATS, quantity_g=500, expiry_date=date.today() + timedelta(days=30)),
        FridgeItem(product=CHICKEN, quantity_g=500, expiry_date=soon),
    ]
    targets = compute_targets(_profile())
    plan = generate_day_plan(fridge, targets, _profile().prefs)
    # breakfast should start with the soonest-expiring product
    first = plan.meals[0].items[0]
    assert first.product_name == CHICKEN.name
    assert first.expiring_soon is True


def test_dietary_filter_excludes_pork_for_halal():
    fridge = [FridgeItem(product=PORK, quantity_g=500)]
    targets = compute_targets(_profile())
    plan = generate_day_plan(fridge, targets, DietaryPrefs(halal=True))
    assert all(it.product_name != PORK.name for m in plan.meals for it in m.items)


def test_recommender_flags_protein_deficit():
    targets = Targets(kcal=2000, protein_g=150, fat_g=60, carbs_g=200)
    planned = Targets(kcal=1000, protein_g=40, fat_g=30, carbs_g=100)
    recs = recommend([CHICKEN, OATS, TOFU], targets, planned, DietaryPrefs())
    assert any("белка" in r.reason for r in recs)
