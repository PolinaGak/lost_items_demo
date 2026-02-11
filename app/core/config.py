from pydantic_settings import BaseSettings
from typing import List

class Config(BaseSettings):
    DEBUG: bool = True

    # PostgreSQL
    POSTGRES_DB: str = "lost_items_db"
    POSTGRES_USER: str = "test_user"
    POSTGRES_PASSWORD: str = "test_pwd"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Telegram Bot
    BOT_TOKEN: str = ""

    # FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "secret_key"

    # PGVector
    VECTOR_DIMENSION: int = 384

    # Admin IDs
    ADMIN_IDS: List[int] = []

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

config = Config()