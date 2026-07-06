"""Open Food Facts lookup — OWNER: Backend-2.

Website (not app): search products by NAME, and optionally by barcode.
Endpoint (no key needed):
  https://world.openfoodfacts.org/cgi/search.pl?search_terms=<q>&json=1&page_size=10
Map product_name + nutriments (energy-kcal_100g, proteins_100g, fat_100g,
carbohydrates_100g) into schemas.Product, then persist via models.Product.

Stub returns nothing so the app runs without network.
"""
from __future__ import annotations

import httpx

from app.schemas import Product

_OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
_OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
_USER_AGENT = "PandaBook/1.0 (hackathon)"


def _float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _map_off_raw(raw: dict) -> Product | None:
    name = (raw.get("product_name") or raw.get("product_name_ru") or "").strip()
    if not name:
        return None
    nut = raw.get("nutriments") or {}
    kcal = nut.get("energy-kcal_100g")
    if kcal is None and nut.get("energy_100g") is not None:
        kcal = _float(nut["energy_100g"]) / 4.184
    categories = (raw.get("categories") or "other").split(",")[0].strip().lower()
    barcode = raw.get("code") or raw.get("_id")
    return Product(
        name=name,
        category=categories or "other",
        kcal_100=_float(kcal),
        protein_100=_float(nut.get("proteins_100g")),
        fat_100=_float(nut.get("fat_100g")),
        carbs_100=_float(nut.get("carbohydrates_100g")),
        tags=[],
        off_barcode=str(barcode) if barcode else None,
    )


def lookup_barcode(barcode: str) -> Product | None:
    try:
        resp = httpx.get(
            _OFF_PRODUCT.format(barcode=barcode),
            timeout=10,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        raw = resp.json().get("product")
        return _map_off_raw(raw) if raw else None
    except httpx.HTTPError:
        return None


def search_products(query: str, limit: int = 10) -> list[Product]:
    try:
        resp = httpx.get(
            _OFF_SEARCH,
            params={"search_terms": query, "json": 1, "page_size": limit},
            timeout=10,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        out: list[Product] = []
        for raw in resp.json().get("products", []):
            p = _map_off_raw(raw)
            if p is not None:
                out.append(p)
        return out
    except httpx.HTTPError:
        return []
