import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Item
from app.schemas import ItemIn, ItemOut

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Item))).all())


@router.post("", response_model=ItemOut, status_code=201)
async def create_item(payload: ItemIn, db: AsyncSession = Depends(get_db)):
    item = Item(id=str(uuid.uuid4()), **payload.model_dump())
    db.add(item)
    await db.commit()
    return item


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: str, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return item
