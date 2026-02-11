from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union

# Загружаем модель один раз
_model = None


def get_model():
    """Ленивая загрузка модели."""
    global _model
    if _model is None:
        print("🔄 Загрузка модели sentence-transformers...")
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("✅ Модель загружена")
    return _model


async def get_embedding(text: Union[str, List[str]]) -> List[float]:
    """
    Получение эмбеддинга для текста.
    Для демостенда - синхронная обёртка над асинхронным интерфейсом.
    """
    model = get_model()

    if isinstance(text, str):
        embedding = model.encode(text)
        return embedding.tolist()
    else:
        embeddings = model.encode(text)
        return [emb.tolist() for emb in embeddings]