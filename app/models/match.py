from sqlalchemy import Column, Integer, Float, ForeignKey, String, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True)
    lost_item_id = Column(Integer, ForeignKey('lost_items.id'), nullable=False)
    found_item_id = Column(Integer, ForeignKey('found_items.id'), nullable=False)

    similarity = Column(Float)
    status = Column(String, default='pending', index=True)

    notified_at = Column(DateTime(timezone=True))
    responded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lost_item = relationship("LostItem", back_populates="matches")
    found_item = relationship("FoundItem", back_populates="matches")

    __table_args__ = (
        Index('ix_unique_match', lost_item_id, found_item_id, unique=True),
    )