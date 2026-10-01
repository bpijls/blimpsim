from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config, read from .env. Nothing is hardcoded elsewhere."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///:memory:"

    # Required — no default, so a missing key fails at startup, not mid-request.
    vonk_key: str
    vonk_base_url: str = "http://vonk:4000/v1"
    vonk_model: str = "code"
    vonk_embed_model: str = "embedding"

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
