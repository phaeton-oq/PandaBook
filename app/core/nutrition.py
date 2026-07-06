"""Calorie & macro targets from a user profile.

BMR: Mifflin-St Jeor. TDEE = BMR * activity factor.
Target kcal adjusts for goal; macros split by goal.
"""
from app.schemas import ActivityLevel, Goal, Sex, Targets, UserProfile

_ACTIVITY_FACTOR = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}

_GOAL_KCAL_ADJUST = {Goal.lose: 0.80, Goal.maintain: 1.0, Goal.gain: 1.15}
# grams of protein per kg bodyweight, by goal
_PROTEIN_PER_KG = {Goal.lose: 2.0, Goal.maintain: 1.6, Goal.gain: 1.8}
# share of kcal from fat
_FAT_KCAL_SHARE = 0.27


def bmr(profile: UserProfile) -> float:
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    return base + (5 if profile.sex == Sex.male else -161)


def compute_targets(profile: UserProfile) -> Targets:
    tdee = bmr(profile) * _ACTIVITY_FACTOR[profile.activity]
    kcal = tdee * _GOAL_KCAL_ADJUST[profile.goal]

    protein_g = _PROTEIN_PER_KG[profile.goal] * profile.weight_kg
    fat_g = (kcal * _FAT_KCAL_SHARE) / 9
    carbs_kcal = kcal - protein_g * 4 - fat_g * 9
    carbs_g = max(carbs_kcal, 0) / 4

    return Targets(
        kcal=round(kcal),
        protein_g=round(protein_g),
        fat_g=round(fat_g),
        carbs_g=round(carbs_g),
    )
