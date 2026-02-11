from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, Numeric, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import NUMERIC

from app.database import Base


class Station(Base):
    __tablename__ = 'stations'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    line_id = Column(Integer, ForeignKey('lines.id'), nullable=False, index=True)
    previous_station_id = Column(Integer, ForeignKey('stations.id'), nullable=True)
    next_station_id = Column(Integer, ForeignKey('stations.id'), nullable=True)
    order_number = Column(Integer)
    latitude = Column(NUMERIC(10, 8))
    longitude = Column(NUMERIC(11, 8))
    is_active = Column(Boolean, default=True)
    opening_date = Column(Date)

    line = relationship("Line", back_populates="stations")

    previous_station = relationship(
        "Station",
        remote_side=[id],
        foreign_keys=[previous_station_id],
        backref="next_stations"
    )
    next_station = relationship(
        "Station",
        remote_side=[id],
        foreign_keys=[next_station_id],
        backref="previous_stations"
    )

    lost_items = relationship("LostItem", back_populates="station")
    found_items = relationship("FoundItem", back_populates="station")

    transfers_as_1 = relationship(
        "TransferPoint",
        foreign_keys="TransferPoint.station_id_1",
        back_populates="station_1"
    )
    transfers_as_2 = relationship(
        "TransferPoint",
        foreign_keys="TransferPoint.station_id_2",
        back_populates="station_2"
    )