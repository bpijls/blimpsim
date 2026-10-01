from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required — shared with the api and the simulator. No default.
    sim_secret: str
    datasets_dir: str = "/datasets"


settings = Settings()
