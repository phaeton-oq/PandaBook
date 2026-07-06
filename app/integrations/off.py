"""Open Food Facts lookup — OWNER: Backend-2.

Website (not app): search products by NAME, and optionally by barcode.
Endpoint (no key needed):
  https://world.openfoodfacts.org/cgi/search.pl?search_terms=<q>&json=1&page_size=10
Map product_name + nutriments (energy-kcal_100g, proteins_100g, fat_100g,
carbohydrates_100g) into schemas.Product, then persist via models.Product.

Stub returns nothing so the app runs without network.
"""
from __future__ import annotations

from app.schemas import Product


def search_products(query: str, limit: int = 10) -> list[Product]:
    # TODO(Backend-2): httpx GET the OFF search endpoint, map nutriments -> Product
    return []
