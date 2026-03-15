from functools import lru_cache
from typing import Literal

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Skinny API"
    app_version: str = "0.1.0"
    app_env: Literal["local", "dev", "prod", "test"] = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["*"]

    postgres_server: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "skinny"
    postgres_password: str = "skinny"
    postgres_db: str = "skinny"
    database_url: str | None = None

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-access-secret-key-32-bytes"
    jwt_refresh_secret_key: str = "change-me-refresh-secret-key-32bytes"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14

    anthropic_api_key: str | None = None
    pinecone_api_key: str | None = None
    pinecone_index_name: str = "skinny-ingredients"
    pinecone_environment: str = "us-east-1"
    ocr_provider: str = "google-ml-kit"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
