from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple

from app.models import FoundItem


async def find_similar_items(
        session: AsyncSession,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.6
) -> List[Tuple[FoundItem, float]]:
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

    stmt = select(
        FoundItem,
        text(f"1 - (embedding <=> '{embedding_str}')").label('similarity')
    ).where(
        text(f"1 - (embedding <=> '{embedding_str}') > {similarity_threshold}")
    ).order_by(
        text('similarity DESC')
    ).limit(limit)

    result = await session.execute(stmt)

    items = []
    for row in result:
        items.append((row[0], float(row[1])))

    return items