"""Fridge CRUD — OWNER: Backend-2.

Persist per-user fridge contents (models.FridgeItem) and expose:
  GET    /api/fridge                list items
  POST   /api/fridge                add item (product_id or name+off_barcode, quantity_g, expiry_date)
  PATCH  /api/fridge/{item_id}      update quantity / expiry
  DELETE /api/fridge/{item_id}      remove item
Use app.db.converters.fridge_to_schema for responses.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.auth_utils import get_current_user
from app.db import models
from app.db.converters import fridge_to_schema
from app.db.session import get_db
from app.integrations.off import lookup_barcode, search_products
from app.schemas import FridgeItem, Product

router = APIRouter(prefix="/api/fridge", tags=["fridge"])


class FridgeItemOut(BaseModel):
    id: int
    item: FridgeItem


class FridgeListResponse(BaseModel):
    items: list[FridgeItemOut]


class AddFridgeRequest(BaseModel):
    product_id: int | None = None
    name: str | None = None
    off_barcode: str | None = None
    quantity_g: float = Field(gt=0)
    expiry_date: date | None = None


class UpdateFridgeRequest(BaseModel):
    quantity_g: float | None = Field(default=None, gt=0)
    expiry_date: date | None = None


def _resolve_product(db: Session, req: AddFridgeRequest) -> models.Product:
    if req.product_id is not None:
        product = db.get(models.Product, req.product_id)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return product

    if req.off_barcode:
        existing = db.scalar(
            select(models.Product).where(models.Product.off_barcode == req.off_barcode)
        )
        if existing is not None:
            return existing
        off_product = lookup_barcode(req.off_barcode)
        if off_product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found in Open Food Facts")
        return _persist_product(db, off_product)

    if req.name:
        existing = db.scalar(select(models.Product).where(models.Product.name == req.name))
        if existing is not None:
            return existing
        matches = search_products(req.name, limit=1)
        if matches:
            return _persist_product(db, matches[0])
        return _persist_product(db, Product(name=req.name, kcal_100=0, protein_100=0, fat_100=0, carbs_100=0))

    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide product_id or name/off_barcode")


def _persist_product(db: Session, p: Product) -> models.Product:
    if p.off_barcode:
        existing = db.scalar(
            select(models.Product).where(models.Product.off_barcode == p.off_barcode)
        )
        if existing is not None:
            return existing
    row = models.Product(
        name=p.name,
        category=p.category,
        kcal_100=p.kcal_100,
        protein_100=p.protein_100,
        fat_100=p.fat_100,
        carbs_100=p.carbs_100,
        tags_csv=",".join(p.tags),
        off_barcode=p.off_barcode,
    )
    db.add(row)
    db.flush()
    return row


def _item_out(item: models.FridgeItem) -> FridgeItemOut:
    return FridgeItemOut(id=item.id, item=fridge_to_schema(item))


def _get_owned_item(db: Session, user_id: int, item_id: int) -> models.FridgeItem:
    item = db.scalar(
        select(models.FridgeItem)
        .where(models.FridgeItem.id == item_id, models.FridgeItem.user_id == user_id)
        .options(joinedload(models.FridgeItem.product))
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fridge item not found")
    return item


@router.get("", response_model=FridgeListResponse)
def list_fridge(
    user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> FridgeListResponse:
    items = db.scalars(
        select(models.FridgeItem)
        .where(models.FridgeItem.user_id == user.id)
        .options(joinedload(models.FridgeItem.product))
        .order_by(models.FridgeItem.id)
    ).all()
    return FridgeListResponse(items=[_item_out(i) for i in items])


@router.post("", response_model=FridgeItemOut, status_code=status.HTTP_201_CREATED)
def add_fridge_item(
    req: AddFridgeRequest,
    user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> FridgeItemOut:
    product = _resolve_product(db, req)
    item = models.FridgeItem(
        user_id=user.id,
        product_id=product.id,
        quantity_g=req.quantity_g,
        expiry_date=req.expiry_date,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item.product = product
    return _item_out(item)


@router.patch("/{item_id}", response_model=FridgeItemOut)
def update_fridge_item(
    item_id: int,
    req: UpdateFridgeRequest,
    user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> FridgeItemOut:
    item = _get_owned_item(db, user.id, item_id)
    if req.quantity_g is not None:
        item.quantity_g = req.quantity_g
    if req.expiry_date is not None:
        item.expiry_date = req.expiry_date
    db.commit()
    db.refresh(item)
    return _item_out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_fridge_item(
    item_id: int,
    user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> Response:
    item = _get_owned_item(db, user.id, item_id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
