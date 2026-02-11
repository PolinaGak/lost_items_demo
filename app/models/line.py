from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Line(Base):
    __tablename__ = 'lines'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    color = Column(String(50), nullable=False)
    number = Column(Integer)
    description = Column(Text)

    stations = relationship("Station", back_populates="line")
    transfers_from = relationship(
        "TransferPoint",
        foreign_keys="TransferPoint.line_id_1",
        back_populates="line_from"
    )
    transfers_to = relationship(
        "TransferPoint",
        foreign_keys="TransferPoint.line_id_2",
        back_populates="line_to"
    )