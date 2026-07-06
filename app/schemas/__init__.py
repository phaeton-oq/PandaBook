"""Shared Pydantic contract for PandaBook.

FROZEN INTERFACE. Both backends and the frontend build against these.
Change only by team agreement — a change here ripples everywhere.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Sex(str, Enum):
    male = "male"
    female = "female"


class Goal(str, Enum):
    lose = "lose"
    maintain = "maintain"
    gain = "gain"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class DietaryPrefs(BaseModel):
    vegan: bool = False
    vegetarian: bool = False
    halal: bool = False
    gluten_free: bool = False
    lactose_free: bool = False
    allergens: list[str] = Field(default_factory=list)  # product tags to exclude


class UserProfile(BaseModel):
    sex: Sex
    age: int = Field(ge=1, le=120)
    weight_kg: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    activity: ActivityLevel = ActivityLevel.moderate
    goal: Goal = Goal.maintain
    prefs: DietaryPrefs = Field(default_factory=DietaryPrefs)


class Product(BaseModel):
    id: int | None = None
    name: str
    category: str = "other"
    kcal_100: float = Field(ge=0)
    protein_100: float = Field(ge=0)
    fat_100: float = Field(ge=0)
    carbs_100: float = Field(ge=0)
    tags: list[str] = Field(default_factory=list)  # e.g. meat, pork, dairy, gluten, egg, nuts
    off_barcode: str | None = None


class FridgeItem(BaseModel):
    product: Product
    quantity_g: float = Field(gt=0)
    expiry_date: date | None = None


class Targets(BaseModel):
    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float


class MealItem(BaseModel):
    product_name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float
    expiring_soon: bool = False


class Meal(BaseModel):
    type: MealType
    items: list[MealItem] = Field(default_factory=list)
    kcal: float = 0
    protein: float = 0
    fat: float = 0
    carbs: float = 0


class DayPlan(BaseModel):
    day: date
    targets: Targets
    meals: list[Meal] = Field(default_factory=list)
    totals: Targets
    coverage_pct: float  # how much of the calorie target the fridge covered (0..100)
    notes: list[str] = Field(default_factory=list)


class ShoppingItem(BaseModel):
    product_name: str
    grams: float
    reason: str  # e.g. "covers protein deficit"


class Recipe(BaseModel):
    """Produced by the LLM integration (Backend-2)."""
    title: str
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class DayNutrition(BaseModel):
    day: date
    kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    goal_met: bool  # calories landed within the goal band for that day
