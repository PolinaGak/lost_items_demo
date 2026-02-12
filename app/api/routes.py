from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from app.database import get_db
from app.models import LostItem, FoundItem, Station, Line, User, Match
from app.services.embedding import get_embedding
from app.services.matcher import find_similar_items
from pydantic import BaseModel, validator
from datetime import date
import secrets

router = APIRouter(tags=["lost-items"])

class CreateLostItemRequest(BaseModel):
    user_id: int
    description: str
    loss_date: date
    station_id: int

    @validator('description')
    def validate_description(cls, v):
        if len(v) < 10:
            raise ValueError("Описание должно быть не короче 10 символов")
        return v

class LostItemResponse(BaseModel):
    id: int
    description: str
    loss_date: date
    station_name: Optional[str] = None
    status: str

class CreateUserRequest(BaseModel):
    telegram_id: int

async def get_current_user(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")
    result = await db.execute(select(User).where(User.token == authorization))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Неверный токен")
    return user

@router.post("/lost-items")
async def create_lost_item(
        payload: CreateLostItemRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    message = ""

    try:
        embedding = await get_embedding(payload.description)
        lost_item = LostItem(
            user_id=payload.user_id,
            description=payload.description,
            embedding=embedding,
            loss_date=payload.loss_date,
            station_id=payload.station_id,
            status="pending"
        )
        db.add(lost_item)
        await db.commit()
        await db.refresh(lost_item)

        similar_items = await find_similar_items(
            session=db,
            query_embedding=embedding,
            station_id=payload.station_id,
            loss_date=payload.loss_date,
            limit=5,
            similarity_threshold=0.65,
            days_delta=3
        )

        if similar_items:
            lost_item.status = "matched"
            messages = []
            for i, (found_item, similarity) in enumerate(similar_items[:3], 1):
                station = await db.get(Station, found_item.station_id)
                station_name = station.name if station else "неизвестно"

                match = Match(
                    lost_item_id=lost_item.id,
                    found_item_id=found_item.id,
                    similarity=similarity,
                    status='pending'
                )
                db.add(match)

                messages.append(
                    f"{i}. {found_item.description} на станции {station_name}\n"
                    f"   Совпадение: {similarity:.1%}\n"
                    f"   Обратитесь к дежурным за получением"
                )

            message = "Мы нашли похожие вещи!\n\n" + "\n".join(messages)
            await db.commit()
        else:
            message = "Пока не нашли похожих вещей. Заявка сохранена."

        return {"message": message, "lost_item_id": lost_item.id}

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/lost-items/{user_id}")
async def get_user_lost_items(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    result = await db.execute(
        select(LostItem, Station.name.label('station_name'))
        .join(Station, LostItem.station_id == Station.id)
        .where(LostItem.user_id == user_id)
        .order_by(LostItem.created_at.desc())
    )
    items = result.all()
    response_items = []
    for lost_item, station_name in items:
        response_items.append({
            "id": lost_item.id,
            "description": lost_item.description,
            "loss_date": lost_item.loss_date.isoformat(),
            "station_name": station_name,
            "status": lost_item.status
        })
    return response_items

@router.get("/lines")
async def get_lines(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Line).order_by(Line.id))
    return [{"id": l.id, "name": l.name, "color": l.color} for l in result.scalars().all()]

@router.get("/stations")
async def get_stations(line_id: Optional[int] = None, page: int = 0, per_page: int = 8,
                       db: AsyncSession = Depends(get_db)):
    if line_id is None:
        raise HTTPException(status_code=400, detail="line_id is required for pagination")
    offset = page * per_page
    query = select(Station).where(Station.line_id == line_id).order_by(Station.order_number).limit(per_page).offset(offset)
    result = await db.execute(query)
    page_stations = result.scalars().all()
    count_query = select(func.count()).select_from(Station).where(Station.line_id == line_id)
    total_count = (await db.execute(count_query)).scalar()
    total_pages = (total_count + per_page - 1) // per_page
    return {
        "stations": [{"id": s.id, "name": s.name} for s in page_stations],
        "total_pages": total_pages
    }

@router.get("/stations/search")
async def search_stations(query: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Station, Line.name.label('line_name'))
        .join(Line, Station.line_id == Line.id)
        .where(Station.name.ilike(f"%{query}%"))
        .order_by(Station.name)
        .limit(limit)
    )
    items = result.all()
    return [{
        "id": station.id,
        "name": station.name,
        "line_name": line_name
    } for station, line_name in items]

@router.get("/stations/{station_id}")
async def get_station(station_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Station, Line.name.label('line_name'), Line.color.label('color'))
        .join(Line, Station.line_id == Line.id)
        .where(Station.id == station_id)
    )
    item = result.first()
    if not item:
        raise HTTPException(status_code=404, detail="Station not found")
    station, line_name, color = item
    return {
        "id": station.id,
        "name": station.name,
        "line_name": line_name,
        "color": color
    }

@router.get("/users/by-telegram/{telegram_id}")
async def get_user_by_telegram(telegram_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user.id, "token": user.token}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in get_user_by_telegram for id={telegram_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.post("/users")
async def create_user(payload: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    try:
        existing_result = await db.execute(select(User).where(User.telegram_id == payload.telegram_id))
        existing_user = existing_result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        user = User(
            telegram_id=payload.telegram_id,
            token=secrets.token_hex(32)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {"id": user.id, "token": user.token}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")