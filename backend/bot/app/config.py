"""Ilova sozlamalari. Barcha maxfiy qiymatlar .env dan o'qiladi."""
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_group_id: int = Field(..., alias="ADMIN_GROUP_ID")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    # PostgreSQL
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    db_host: str = Field(default="db", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")

    # Redis
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    # Ollama AI
    ollama_url: str = Field(default="http://host.docker.internal:11434", alias="OLLAMA_URL")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    ai_enabled: bool = Field(default=True, alias="AI_ENABLED")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field
    @property
    def admin_id_list(self) -> list[int]:
        return [
            int(x.strip()) for x in self.admin_ids.split(",") if x.strip().isdigit()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
