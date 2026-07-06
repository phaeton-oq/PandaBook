"""Seed product catalog. KБЖУ per 100g, tags drive dietary filters.

tags vocabulary: meat, pork, fish, egg, dairy, gluten, nuts, honey, alcohol
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product

# name, category, kcal, protein, fat, carbs, tags
CATALOG: list[tuple[str, str, float, float, float, float, list[str]]] = [
    ("Куриная грудка", "meat", 165, 31, 3.6, 0, ["meat"]),
    ("Говядина", "meat", 250, 26, 15, 0, ["meat"]),
    ("Свинина", "meat", 242, 27, 14, 0, ["meat", "pork"]),
    ("Лосось", "fish", 208, 20, 13, 0, ["fish"]),
    ("Тунец консерв.", "fish", 116, 26, 1, 0, ["fish"]),
    ("Яйцо куриное", "egg", 155, 13, 11, 1.1, ["egg"]),
    ("Творог 5%", "dairy", 121, 17, 5, 3, ["dairy"]),
    ("Молоко 2.5%", "dairy", 52, 2.8, 2.5, 4.7, ["dairy"]),
    ("Йогурт натур.", "dairy", 60, 5, 3.2, 4, ["dairy"]),
    ("Сыр твёрдый", "dairy", 364, 25, 29, 2, ["dairy"]),
    ("Овсянка", "grain", 366, 12, 6, 62, ["gluten"]),
    ("Гречка", "grain", 343, 13, 3.4, 62, []),
    ("Рис белый", "grain", 344, 6.7, 0.7, 78, []),
    ("Макароны", "grain", 371, 13, 1.5, 75, ["gluten"]),
    ("Хлеб цельнозерн.", "grain", 247, 9, 3.4, 47, ["gluten"]),
    ("Картофель", "veg", 77, 2, 0.4, 17, []),
    ("Брокколи", "veg", 34, 2.8, 0.4, 7, []),
    ("Помидор", "veg", 18, 0.9, 0.2, 3.9, []),
    ("Огурец", "veg", 15, 0.7, 0.1, 3.6, []),
    ("Морковь", "veg", 41, 0.9, 0.2, 10, []),
    ("Шпинат", "veg", 23, 2.9, 0.4, 3.6, []),
    ("Банан", "fruit", 89, 1.1, 0.3, 23, []),
    ("Яблоко", "fruit", 52, 0.3, 0.2, 14, []),
    ("Авокадо", "fruit", 160, 2, 15, 9, []),
    ("Фасоль", "legume", 333, 21, 2, 54, []),
    ("Чечевица", "legume", 352, 24, 1.5, 63, []),
    ("Нут", "legume", 364, 19, 6, 61, []),
    ("Тофу", "legume", 76, 8, 4.8, 1.9, []),
    ("Миндаль", "nuts", 579, 21, 50, 22, ["nuts"]),
    ("Оливковое масло", "fat", 884, 0, 100, 0, []),
    ("Сливочное масло", "fat", 717, 0.9, 81, 0.1, ["dairy"]),
    ("Мёд", "sweet", 304, 0.3, 0, 82, ["honey"]),
]


def seed_products(db: Session) -> None:
    if db.scalar(select(Product).limit(1)) is not None:
        return
    for name, cat, kcal, p, f, c, tags in CATALOG:
        db.add(Product(
            name=name, category=cat, kcal_100=kcal,
            protein_100=p, fat_100=f, carbs_100=c,
            tags_csv=",".join(tags),
        ))
    db.commit()
