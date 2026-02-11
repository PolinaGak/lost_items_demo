from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import LostItem, FoundItem, Station, Match
from app.services.embedding import get_embedding
from app.services.matcher import find_similar_items

router = APIRouter()

@router.get("/stations")
async def get_stations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Station).order_by(Station.name))
    stations = result.scalars().all()
    return [
        {"id": s.id, "name": s.name, "line_id": s.line_id}
        for s in stations
    ]

@router.get("/lost/{user_id}")
async def get_user_lost_items(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LostItem)
        .where(LostItem.user_id == user_id)
        .order_by(LostItem.created_at.desc())
    )
    items = result.scalars().all()
    return items

@router.get("/found")
async def get_found_items(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FoundItem)
        .order_by(FoundItem.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return items