"""Fridge CRUD — OWNER: Backend-2.

Persist per-user fridge contents (models.FridgeItem) and expose:
  GET    /api/fridge                list items
  POST   /api/fridge                add item (product_id or name+off_barcode, quantity_g, expiry_date)
  PATCH  /api/fridge/{item_id}      update quantity / expiry
  DELETE /api/fridge/{item_id}      remove item
Use app.db.converters.fridge_to_schema for responses.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/fridge", tags=["fridge"])


@router.get("")
def list_fridge():
    # TODO(Backend-2): read models.FridgeItem for the current user
    return {"todo": "fridge listing", "items": []}
