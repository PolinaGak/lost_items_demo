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
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_station_by_name(self, name: str, line_id: Optional[int] = None) -> Optional[Station]:
        query = select(Station).where(Station.name == name)
        if line_id:
            query = query.where(Station.line_id == line_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_transfer_stations(self, station_id: int) -> List[Station]:
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

        result = await self.session.execute(
            select(Station)
            .where(Station.line_id == line_id)
            .order_by(Station.order_number)
        )
        return result.scalars().all()

    async def get_station_with_line(self, station_id: int) -> Tuple[Station, Line]:

        result = await self.session.execute(
            select(Station, Line)
            .join(Line, Station.line_id == Line.id)
            .where(Station.id == station_id)
        )
        return result.first()

    async def expand_search_area(self, station_id: int) -> Set[int]:

        station_ids = {station_id}

        station = await self.session.get(Station, station_id)
        if not station:
            return station_ids

        line_stations = await self.get_line_stations(station.line_id)
        for s in line_stations:
            station_ids.add(s.id)

        transfers = await self.session.execute(
            select(TransferPoint).where(
                or_(
                    TransferPoint.station_id_1 == station_id,
                    TransferPoint.station_id_2 == station_id
                )
            )
        )
        transfers = transfers.scalars().all()

        for t in transfers:
            if t.station_id_1 == station_id:
                transfer_station_id = t.station_id_2
                transfer_line_id = t.line_id_2
            else:
                transfer_station_id = t.station_id_1
                transfer_line_id = t.line_id_1

            station_ids.add(transfer_station_id)

            transfer_line_stations = await self.get_line_stations(transfer_line_id)
            for s in transfer_line_stations:
                station_ids.add(s.id)

        return station_ids

    async def expand_search_area_by_radius(
            self,
            station_id: int,
            radius_km: float = 0.5
    ) -> Set[int]:
        station_ids = {station_id}

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
        start_date = loss_date - timedelta(days=days_delta)
        end_date = loss_date + timedelta(days=days_delta)
        return start_date, end_date


async def find_stations_for_search(
        session: AsyncSession,
        station_name: str,
        line_id: Optional[int] = None,
        expand_lines: bool = True
) -> List[Station]:
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

    service = StationService(session)

    station_ids = await service.expand_search_area(station_id)
    date_start, date_end = await service.get_date_range(loss_date, days_delta)

    return {
        "station_ids": list(station_ids),
        "date_start": date_start,
        "date_end": date_end
    }