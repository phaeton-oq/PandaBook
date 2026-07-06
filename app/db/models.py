from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, default="")
    name: Mapped[str] = mapped_column(String, default="")
    # profile
    sex: Mapped[str] = mapped_column(String, default="male")
    age: Mapped[int] = mapped_column(default=30)
    weight_kg: Mapped[float] = mapped_column(Float, default=70)
    height_cm: Mapped[float] = mapped_column(Float, default=175)
    activity: Mapped[str] = mapped_column(String, default="moderate")
    goal: Mapped[str] = mapped_column(String, default="maintain")
    # dietary prefs stored as CSV of flags/allergens for hackathon simplicity
    prefs_csv: Mapped[str] = mapped_column(String, default="")

    fridge: Mapped[list[FridgeItem]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String, default="other")
    kcal_100: Mapped[float] = mapped_column(Float, default=0)
    protein_100: Mapped[float] = mapped_column(Float, default=0)
    fat_100: Mapped[float] = mapped_column(Float, default=0)
    carbs_100: Mapped[float] = mapped_column(Float, default=0)
    tags_csv: Mapped[str] = mapped_column(String, default="")
    off_barcode: Mapped[str | None] = mapped_column(String, nullable=True)


class FridgeItem(Base):
    __tablename__ = "fridge_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity_g: Mapped[float] = mapped_column(Float, default=0)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(back_populates="fridge")
    product: Mapped[Product] = relationship()


class ConsumptionLog(Base):
    """What the user actually ate — feeds the KБЖУ dashboard."""
    __tablename__ = "consumption_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    day: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String, default="snack")
    grams: Mapped[float] = mapped_column(Float, default=0)
