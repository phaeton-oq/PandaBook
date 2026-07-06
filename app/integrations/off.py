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

# search-a-licious: OFF's dedicated full-text search (reliable JSON, RU support).
# The legacy /cgi/search.pl is flaky (returns HTML/503 on many queries).
_OFF_SEARCH = "https://search.openfoodfacts.org/search"
_OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
_USER_AGENT = "PandaBook/1.0 (hackathon)"


def _float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _name(raw: dict) -> str:
    nm = raw.get("product_name") or raw.get("product_name_ru") or ""
    if isinstance(nm, dict):  # search-a-licious may return a multilingual dict
        nm = nm.get("ru") or nm.get("main") or next(iter(nm.values()), "")
    return str(nm).strip()


# OFF's structured allergen/category tags are mostly empty for RU products, so
# we infer dietary tags from the product name. Rough but it's what drives the
# vegan/halal/gluten/lactose filters for external products.
_NAME_TAGS: dict[str, tuple[str, ...]] = {
    "dairy": ("творог", "молоко", "молочн", "сыр", "йогурт", "сметан", "сливк",
              "кефир", "ряженк", "сливочн", "творож"),
    "meat": ("свинин", "говядин", "куриц", "курин", "индейк", "мясо", "колбас",
             "ветчин", "бекон", "сосиск", "котлет", "фарш", "баранин", "телятин",
             "паштет", "пельмен", "стейк"),
    "pork": ("свинин", "бекон", "ветчин", "сало"),
    "fish": ("рыб", "лосось", "тунец", "сельд", "форел", "треск", "креветк",
             "краб", "икра", "скумбри", "горбуш", "морепродукт"),
    "egg": ("яйц", "яичн", "омлет", "глазунь"),
    "gluten": ("хлеб", "макарон", "мука", "булк", "пшениц", "пицц", "лазан",
               "вафл", "печенье", "сухар", "батон", "лаваш", "пряник", "тесто"),
    "nuts": ("орех", "миндал", "фундук", "арахис", "кешью", "фисташк"),
    "honey": ("мёд", "мед "),
}


def _infer_tags(name: str, raw: dict) -> list[str]:
    text = name.lower()
    tags = {tag for tag, words in _NAME_TAGS.items() if any(w in text for w in words)}
    # OFF allergens as a bonus signal when present
    for a in raw.get("allergens_tags") or []:
        if "milk" in a:
            tags.add("dairy")
        if "gluten" in a:
            tags.add("gluten")
        if "egg" in a:
            tags.add("egg")
        if "nut" in a:
            tags.add("nuts")
        if "fish" in a:
            tags.add("fish")
    return sorted(tags)


def _map_off_raw(raw: dict) -> Product | None:
    name = _name(raw)
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
        tags=_infer_tags(name, raw),
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
            params={
                "q": query,
                "page_size": limit,
                "lang": "ru",
                "fields": "product_name,nutriments,code,categories,allergens_tags",
            },
            timeout=15,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        out: list[Product] = []
        seen: set[str] = set()
        for raw in resp.json().get("hits", []):
            p = _map_off_raw(raw)
            if p is None or p.kcal_100 <= 0:
                continue
            key = p.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out
    except (httpx.HTTPError, ValueError):  # ValueError covers JSON decode errors
        return []
