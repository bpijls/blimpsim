from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config, read from .env. Nothing is hardcoded elsewhere."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///:memory:"

    # The sim gateway runs on the GPU host, next to the Godot simulator.
    sim_gateway_url: str = "http://vonk:8100"
    # Required — no default, so a missing secret fails at startup, not mid-request.
    sim_secret: str

    # Which blimp the api steers: "sim" (the digital twin) or "real" (the hardware).
    blimp_driver: str = "sim"

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
