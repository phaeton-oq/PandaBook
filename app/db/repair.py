"""Startup DB repair — fixes legacy SQLite after schema/auth changes."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.password_utils import hash_password, verify_password
from app.db.models import ConsumptionLog, FridgeItem, Product, User

DEMO_EMAIL = "demo@pandabook.local"
DEMO_PASSWORD = "demo12345"

_FULL_DAY = [("Куриная грудка", 300), ("Рис белый", 250), ("Овсянка", 100),
             ("Яйцо куриное", 150), ("Банан", 120), ("Оливковое масло", 15)]
_HALF_DAY = [("Куриная грудка", 150), ("Рис белый", 120)]


def repair_schema(engine: Engine) -> None:
    """Add columns introduced after first deploy (SQLite has no auto-migrate)."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "password_hash" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR NOT NULL DEFAULT ''"
            ))


def _seed_demo_history(db: Session, user_id: int) -> None:
    if db.scalar(select(ConsumptionLog).where(ConsumptionLog.user_id == user_id).limit(1)):
        return
    by_name = {p.name: p for p in db.scalars(select(Product)).all()}
    today = date.today()
    schedule = [(0, _FULL_DAY), (1, _FULL_DAY), (2, _FULL_DAY), (3, _HALF_DAY), (4, _HALF_DAY)]
    for offset, menu in schedule:
        day = today - timedelta(days=offset)
        for pname, grams in menu:
            product = by_name.get(pname)
            if product:
                db.add(ConsumptionLog(
                    user_id=user_id, product_id=product.id,
                    day=day, meal_type="mixed", grams=grams,
                ))


def ensure_demo_user(db: Session) -> None:
    """Demo account always works — even if DB was created before password auth."""
    pwd_hash = hash_password(DEMO_PASSWORD)
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL, name="Demo", password_hash=pwd_hash,
            sex="male", age=25, weight_kg=78, height_cm=182,
            activity="moderate", goal="lose",
        )
        db.add(user)
        db.flush()
    elif not user.password_hash or not verify_password(DEMO_PASSWORD, user.password_hash):
        user.password_hash = pwd_hash
    _seed_demo_history(db, user.id)
    db.commit()


def repair_legacy_users(db: Session) -> None:
    """Remove old pre-password accounts that can't log in and have no data."""
    stale = db.scalars(
        select(User).where(User.email != DEMO_EMAIL, User.password_hash == "")
    ).all()
    deleted = False
    for user in stale:
        has_data = (
            db.scalar(select(ConsumptionLog).where(ConsumptionLog.user_id == user.id).limit(1))
            or db.scalar(select(FridgeItem).where(FridgeItem.user_id == user.id).limit(1))
        )
        if has_data:
            continue
        db.delete(user)
        deleted = True
    if deleted:
        db.commit()


def repair_database(db: Session) -> None:
    ensure_demo_user(db)
    repair_legacy_users(db)
