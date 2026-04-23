from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    database_url: str = 'postgresql+psycopg://postgres:postgres@localhost:5432/dj_lineage'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
