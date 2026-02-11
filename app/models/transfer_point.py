from sqlalchemy import Column, Integer, ForeignKey, String, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class TransferPoint(Base):
    __tablename__ = 'transfer_points'

    id = Column(Integer, primary_key=True)
    station_id_1 = Column(Integer, ForeignKey('stations.id'), nullable=False)
    station_id_2 = Column(Integer, ForeignKey('stations.id'), nullable=False)
    line_id_1 = Column(Integer, ForeignKey('lines.id'), nullable=False)
    line_id_2 = Column(Integer, ForeignKey('lines.id'), nullable=False)

    transfer_type = Column(String(50))  # 'cross-platform', 'underground', 'street', 'mcd', 'mck'
    transfer_time_minutes = Column(Integer, default=3)
    distance_meters = Column(Integer)
    is_wheelchair_accessible = Column(Boolean, default=False)
    notes = Column(Text)

    station_1 = relationship(
        "Station",
        foreign_keys=[station_id_1],
        back_populates="transfers_as_1"
    )
    station_2 = relationship(
        "Station",
        foreign_keys=[station_id_2],
        back_populates="transfers_as_2"
    )

    line_from = relationship(
        "Line",
        foreign_keys=[line_id_1],
        back_populates="transfers_from"
    )
    line_to = relationship(
        "Line",
        foreign_keys=[line_id_2],
        back_populates="transfers_to"
    )

    __table_args__ = (
        UniqueConstraint('station_id_1', 'station_id_2', name='unique_transfer'),
    )