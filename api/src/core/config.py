from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/waast360",
        description="PostgreSQL Connection URL",
    )
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")


settings = Settings()
