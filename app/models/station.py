from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Station(Base):
    __tablename__ = 'stations'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    line_id = Column(Integer, nullable=False, index=True)

    lost_items = relationship("LostItem", back_populates="station")
    found_items = relationship("FoundItem", back_populates="station")