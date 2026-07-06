from datetime import date, timedelta

from app.core.progress import current_streak, daily_nutrition, panda_mood
from app.schemas import Product

RICE = Product(name="Рис белый", kcal_100=344, protein_100=6.7, fat_100=0.7, carbs_100=78)


def _entries_for(days_kcal: dict[date, float]):
    # build entries hitting a target kcal per day using rice as filler
    entries = []
    for day, kcal in days_kcal.items():
        grams = kcal / (RICE.kcal_100 / 100)
        entries.append((day, RICE, grams))
    return entries


def test_daily_nutrition_aggregates_and_flags_goal():
    today = date.today()
    entries = _entries_for({today: 2000})
    days = daily_nutrition(entries, target_kcal=2000)
    assert len(days) == 1
    assert days[0].goal_met is True
    assert abs(days[0].kcal - 2000) < 5


def test_goal_not_met_when_far_below():
    today = date.today()
    days = daily_nutrition(_entries_for({today: 800}), target_kcal=2000)
    assert days[0].goal_met is False


def test_streak_counts_recent_consecutive():
    t = date.today()
    entries = _entries_for({t - timedelta(days=2): 2000,
                            t - timedelta(days=1): 2000,
                            t: 2000})
    days = daily_nutrition(entries, target_kcal=2000)
    assert current_streak(days) == 3


def test_streak_breaks_on_miss():
    t = date.today()
    entries = _entries_for({t - timedelta(days=2): 800,   # miss
                            t - timedelta(days=1): 2000,
                            t: 2000})
    days = daily_nutrition(entries, target_kcal=2000)
    assert current_streak(days) == 2


def test_panda_mood_levels():
    assert panda_mood(3, True)[0] == "🐼✨"
    assert panda_mood(1, False)[0] == "🐼"
    assert panda_mood(0, False)[0] == "🐼💤"
