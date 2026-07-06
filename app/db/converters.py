"""Model <-> schema converters. Keeps core/ independent of SQLAlchemy."""
from app.db import models
from app import schemas


def parse_prefs(csv: str) -> schemas.DietaryPrefs:
    flags = {t.strip() for t in csv.split(",") if t.strip()}
    known = {"vegan", "vegetarian", "halal", "gluten_free", "lactose_free"}
    return schemas.DietaryPrefs(
        vegan="vegan" in flags,
        vegetarian="vegetarian" in flags,
        halal="halal" in flags,
        gluten_free="gluten_free" in flags,
        lactose_free="lactose_free" in flags,
        allergens=sorted(flags - known),
    )


def product_to_schema(p: models.Product) -> schemas.Product:
    return schemas.Product(
        id=p.id, name=p.name, category=p.category,
        kcal_100=p.kcal_100, protein_100=p.protein_100,
        fat_100=p.fat_100, carbs_100=p.carbs_100,
        tags=[t for t in p.tags_csv.split(",") if t],
        off_barcode=p.off_barcode,
    )


def fridge_to_schema(item: models.FridgeItem) -> schemas.FridgeItem:
    return schemas.FridgeItem(
        product=product_to_schema(item.product),
        quantity_g=item.quantity_g,
        expiry_date=item.expiry_date,
    )


def user_to_profile(u: models.User) -> schemas.UserProfile:
    return schemas.UserProfile(
        sex=u.sex, age=u.age, weight_kg=u.weight_kg, height_cm=u.height_cm,
        activity=u.activity, goal=u.goal, prefs=parse_prefs(u.prefs_csv),
    )
