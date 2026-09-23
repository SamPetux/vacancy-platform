"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime configuration for API, workers, and shared services."""

    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, _BACKEND_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "vacancy-platform"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://vacancy:vacancy@localhost:5432/vacancy"
    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    telegram_bot_token: SecretStr | None = None

    # VK — prefer service token; never log secret values
    vk_client_id: str | None = None
    vk_client_secret: SecretStr | None = None
    vk_service_token: SecretStr | None = None
    vk_token: SecretStr | None = None  # legacy alias
    vk_api_version: str = "5.199"

    # SuperJob API 2.0 — X-Api-App-Id header uses secret key
    superjob_client_id: str | None = None
    superjob_secret_key: SecretStr | None = None

    llm_api_key: SecretStr | None = None
    sentry_dsn: str | None = None

    # Collection defaults
    collection_lookback_hours: int = 48
    dedup_window_days: int = 7
    vk_posts_per_source: int = 50
    superjob_vacancies_per_run: int = 60
    trudvsem_vacancies_per_run: int = 100  # legacy alias; page size is fixed at 100
    trudvsem_max_pages: int = 150  # safety cap (~15k rows) for full regional snapshot
    feed_target_size: int = 30

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    def vk_access_token(self) -> str | None:
        """Return VK access token without logging it."""
        for candidate in (self.vk_service_token, self.vk_token):
            if candidate is not None:
                value = candidate.get_secret_value().strip()
                if value:
                    return value
        return None


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
