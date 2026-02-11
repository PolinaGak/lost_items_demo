"""
Сервис для работы со станциями метро.
Поиск по пересадкам, веткам, радиусу.
"""
from datetime import datetime, timedelta
from typing import List, Set, Tuple, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Station, TransferPoint, Line


class StationService:
    """Сервис для работы со станциями метро."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_station_by_name(self, name: str, line_id: Optional[int] = None) -> Optional[Station]:
        """
        Получить станцию по названию и опционально по линии.
        """
        query = select(Station).where(Station.name == name)
        if line_id:
            query = query.where(Station.line_id == line_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_transfer_stations(self, station_id: int) -> List[Station]:
        """
        Получить все станции, на которые можно перейти с данной.
        Прямые пересадки.
        """
        transfers = await self.session.execute(
            select(TransferPoint).where(
                or_(
                    TransferPoint.station_id_1 == station_id,
                    TransferPoint.station_id_2 == station_id
                )
            )
        )
        transfers = transfers.scalars().all()

        station_ids = set()
        for t in transfers:
            if t.station_id_1 == station_id:
                station_ids.add(t.station_id_2)
            else:
                station_ids.add(t.station_id_1)

        if not station_ids:
            return []

        result = await self.session.execute(
            select(Station).where(Station.id.in_(station_ids))
        )
        return result.scalars().all()

    async def get_line_stations(self, line_id: int) -> List[Station]:
        """
        Получить все станции одной ветки (линии).
        """
        result = await self.session.execute(
            select(Station)
            .where(Station.line_id == line_id)
            .order_by(Station.order_number)
        )
        return result.scalars().all()

    async def get_station_with_line(self, station_id: int) -> Tuple[Station, Line]:
        """
        Получить станцию вместе с её линией.
        """
        result = await self.session.execute(
            select(Station, Line)
            .join(Line, Station.line_id == Line.id)
            .where(Station.id == station_id)
        )
        return result.first()

    async def expand_search_area(self, station_id: int) -> Set[int]:
        """
        РАСШИРЕНИЕ ПОИСКА ПО ПРИНЦИПУ:
        1. Исходная станция
        2. Все прямые пересадки с неё
        3. ВСЕ станции ВСЕХ линий, которые затронуты (и исходная линия, и линии пересадок)

        Аргументы:
            station_id: ID станции, с которой начинаем поиск

        Возвращает:
            Set[int] - множество ID станций для поиска
        """
        station_ids = {station_id}

        # Получаем исходную станцию и её линию
        station = await self.session.get(Station, station_id)
        if not station:
            return station_ids

        # Добавляем ВСЮ линию исходной станции
        line_stations = await self.get_line_stations(station.line_id)
        for s in line_stations:
            station_ids.add(s.id)

        # Получаем все прямые пересадки
        transfers = await self.session.execute(
            select(TransferPoint).where(
                or_(
                    TransferPoint.station_id_1 == station_id,
                    TransferPoint.station_id_2 == station_id
                )
            )
        )
        transfers = transfers.scalars().all()

        # Для каждой пересадки:
        # 1. Добавляем саму станцию пересадки
        # 2. Добавляем ВСЮ линию этой станции
        for t in transfers:
            if t.station_id_1 == station_id:
                transfer_station_id = t.station_id_2
                transfer_line_id = t.line_id_2
            else:
                transfer_station_id = t.station_id_1
                transfer_line_id = t.line_id_1

            station_ids.add(transfer_station_id)

            # Добавляем всю линию станции пересадки
            transfer_line_stations = await self.get_line_stations(transfer_line_id)
            for s in transfer_line_stations:
                station_ids.add(s.id)

        return station_ids

    async def expand_search_area_by_radius(
            self,
            station_id: int,
            radius_km: float = 0.5
    ) -> Set[int]:
        """
        Расширение поиска по пешеходному радиусу (500м).
        Использует таблицу transfer_points с distance_meters.
        """
        station_ids = {station_id}

        # Пересадки в пределах радиуса
        transfers = await self.session.execute(
            select(TransferPoint)
            .where(
                or_(
                    TransferPoint.station_id_1 == station_id,
                    TransferPoint.station_id_2 == station_id
                )
            )
            .where(
                TransferPoint.distance_meters <= radius_km * 1000
            )
        )
        transfers = transfers.scalars().all()

        for t in transfers:
            if t.station_id_1 == station_id:
                station_ids.add(t.station_id_2)
                station_ids.update(await self.get_line_stations(t.line_id_2))
            else:
                station_ids.add(t.station_id_1)
                station_ids.update(await self.get_line_stations(t.line_id_1))

        return station_ids

    async def get_date_range(self, loss_date: datetime.date, days_delta: int = 3) -> Tuple[
        datetime.date, datetime.date]:
        """
        Получить диапазон дат для поиска: указанная дата ± days_delta.

        Аргументы:
            loss_date: дата потери
            days_delta: количество дней до/после (по умолчанию 3)

        Возвращает:
            Tuple[start_date, end_date]
        """
        start_date = loss_date - timedelta(days=days_delta)
        end_date = loss_date + timedelta(days=days_delta)
        return start_date, end_date


# ============================================================================
# ФУНКЦИИ ДЛЯ БЫСТРОГО ИСПОЛЬЗОВАНИЯ (НЕ ЗАВИСЯТ ОТ КЛАССА)
# ============================================================================

async def find_stations_for_search(
        session: AsyncSession,
        station_name: str,
        line_id: Optional[int] = None,
        expand_lines: bool = True
) -> List[Station]:
    """
    Удобная функция для поиска станций по названию с автоматическим расширением.

    Пример:
        stations = await find_stations_for_search(session, "Добрынинская")
        # Вернёт: [Добрынинская, Серпуховская, ... вся 5 и 9 линии]
    """
    service = StationService(session)

    station = await service.get_station_by_name(station_name, line_id)
    if not station:
        return []

    if expand_lines:
        station_ids = await service.expand_search_area(station.id)
        result = await session.execute(
            select(Station).where(Station.id.in_(station_ids))
        )
        return result.scalars().all()
    else:
        return [station]


async def build_search_query(
        session: AsyncSession,
        station_id: int,
        loss_date: datetime.date,
        days_delta: int = 3
) -> dict:
    """
    Собрать все параметры для поискового запроса.

    Возвращает словарь с:
        - station_ids: список ID станций для поиска
        - date_start: начальная дата
        - date_end: конечная дата
    """
    service = StationService(session)

    station_ids = await service.expand_search_area(station_id)
    date_start, date_end = await service.get_date_range(loss_date, days_delta)

    return {
        "station_ids": list(station_ids),
        "date_start": date_start,
        "date_end": date_end
    }