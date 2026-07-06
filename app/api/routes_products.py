"""Product catalog + search (Backend-1).

GET /api/products          : our known catalog, for the fridge quick-pick UI.
GET /api/products/search   : live Open Food Facts search, for autocomplete.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.converters import product_to_schema
from app.db.session import get_db
from app.integrations.off import lookup_barcode, search_products
from app.schemas import Product

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[Product])
def list_products(q: str | None = None, db: Session = Depends(get_db)) -> list[Product]:
    rows = db.scalars(select(models.Product).order_by(models.Product.name)).all()
    products = [product_to_schema(p) for p in rows]
    if q:
        # filter in Python: SQLite LIKE isn't case-insensitive for Cyrillic
        needle = q.lower()
        products = [p for p in products if needle in p.name.lower()]
    return products


@router.get("/search", response_model=list[Product])
def search(q: str, limit: int = 10) -> list[Product]:
    """Live Open Food Facts search — returns candidates with КБЖУ to pick from."""
    return search_products(q, limit=limit)


@router.get("/barcode/{code}", response_model=Product)
def by_barcode(code: str) -> Product:
    """Open Food Facts lookup by EAN/barcode."""
    product = lookup_barcode(code.strip())
    if product is None:
        raise HTTPException(404, "Product not found")
    return product
