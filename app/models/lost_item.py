from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Text, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class LostItem(Base):
    __tablename__ = 'lost_items'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    description = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    loss_date = Column(Date, nullable=False)
    station_id = Column(Integer, ForeignKey('stations.id'), nullable=False)

    status = Column(String, default='pending', index=True)
    is_found = Column(Boolean, default=False)
    is_taken = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="lost_items")
    station = relationship("Station", back_populates="lost_items")
    matches = relationship("Match", back_populates="lost_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_lost_items_status_created', status, created_at.desc()),
    )