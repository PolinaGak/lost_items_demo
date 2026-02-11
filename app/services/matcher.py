from sqlalchemy import select, literal_column, Float, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple, Optional
from datetime import date

from app.models import FoundItem
from app.services.station_service import build_search_query


async def find_similar_items(
        session: AsyncSession,
        query_embedding: List[float],
        station_id: Optional[int] = None,
        loss_date: Optional[date] = None,
        limit: int = 5,
        similarity_threshold: float = 0.6,
        days_delta: int = 3
) -> List[Tuple[FoundItem, float]]:
    """
    Поиск похожих найденных вещей с фильтрацией по:
    - вектору описания (семантический поиск)
    - станциям (исходная + пересадки + вся линия)
    - дате (loss_date ± days_delta)
    """
    # Базовый запрос
    stmt = select(FoundItem)

    # 1. ВЕКТОРНЫЙ ПОИСК (обязательно)
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    similarity_expr = literal_column(
        f"1 - (embedding <=> '{embedding_str}')"
    ).cast(Float)

    stmt = stmt.add_columns(similarity_expr.label('similarity'))
    stmt = stmt.where(similarity_expr > similarity_threshold)

    # 2. ФИЛЬТР ПО СТАНЦИЯМ (если указана станция)
    if station_id:
        params = await build_search_query(session, station_id, loss_date, days_delta)
        stmt = stmt.where(FoundItem.station_id.in_(params["station_ids"]))

    # 3. ФИЛЬТР ПО ДАТЕ (если указана дата)
    if loss_date:
        date_range = await build_search_query(session, station_id, loss_date, days_delta)
        stmt = stmt.where(
            and_(
                FoundItem.found_date >= date_range["date_start"],
                FoundItem.found_date <= date_range["date_end"]
            )
        )

    # Сортировка по похожести
    stmt = stmt.order_by(similarity_expr.desc()).limit(limit)

    result = await session.execute(stmt)

    items = []
    for row in result:
        items.append((row[0], float(row[1])))

    return items


async def find_similar_items_by_name(
        session: AsyncSession,
        query_embedding: List[float],
        station_name: str,
        loss_date: date,
        limit: int = 5,
        similarity_threshold: float = 0.6
) -> List[Tuple[FoundItem, float]]:
    """
    Удобная обёртка: поиск по названию станции вместо ID.
    """
    from app.models import Station

    station = await session.execute(
        select(Station).where(Station.name == station_name)
    )
    station = station.scalar_one_or_none()

    if not station:
        return []

    return await find_similar_items(
        session=session,
        query_embedding=query_embedding,
        station_id=station.id,
        loss_date=loss_date,
        limit=limit,
        similarity_threshold=similarity_threshold
    )