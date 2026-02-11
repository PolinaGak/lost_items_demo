from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class FoundItem(Base):
    __tablename__ = 'found_items'

    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    found_date = Column(Date, nullable=False)
    station_id = Column(Integer, ForeignKey('stations.id'), nullable=False)

    source = Column(String, default='metro')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="found_items")
    matches = relationship("Match", back_populates="found_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            'ix_found_items_embedding',
            embedding,
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )