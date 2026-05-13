from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="sqlite:///./dj_panel.db",
        validation_alias=AliasChoices("DATABASE_URL", "DJ_PANEL_DATABASE_URL"),
    )
    app_env: str = Field(
        default="dev",
        validation_alias=AliasChoices("APP_ENV", "DJ_PANEL_APP_ENV"),
    )
    claim_lease_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices(
            "CLAIM_LEASE_SECONDS", "DJ_PANEL_CLAIM_LEASE_SECONDS"
        ),
    )
    base_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias=AliasChoices("BASE_URL", "DJ_PANEL_BASE_URL"),
    )
    api_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("HOST", "DJ_PANEL_HOST"),
    )
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "DJ_PANEL_PORT"),
    )
    web_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("DJ_PANEL_WEB_HOST"),
    )
    web_port: int = Field(
        default=1337,
        validation_alias=AliasChoices("DJ_PANEL_WEB_PORT"),
    )
    web_dir: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DJ_PANEL_WEB_DIR"),
    )
    web_open: bool = Field(
        default=False,
        validation_alias=AliasChoices("DJ_PANEL_WEB_OPEN"),
    )
    npm_bin: str = Field(
        default="npm",
        validation_alias=AliasChoices("DJ_PANEL_NPM_BIN"),
    )
    http_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "HTTP_TIMEOUT_SECONDS", "DJ_PANEL_HTTP_TIMEOUT_SECONDS"
        ),
    )
    worker_workdir: str = Field(
        default="/tmp/dj-panel-worker",
        validation_alias=AliasChoices("DJ_PANEL_WORKDIR"),
    )
    worker_poll_interval_seconds: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "DJ_PANEL_WORKER_POLL_INTERVAL_SECONDS",
            "DJ_PANEL_POLL_INTERVAL_SECONDS",
        ),
    )
    dj_bin: str = Field(
        default="dj-process",
        validation_alias=AliasChoices("DJ_PANEL_DJ_BIN"),
    )
    dj_config_arg: str = Field(
        default="--config",
        validation_alias=AliasChoices("DJ_PANEL_DJ_CONFIG_ARG"),
    )
    recipe_timeout_seconds: int = Field(
        default=7200,
        validation_alias=AliasChoices("DJ_PANEL_RECIPE_TIMEOUT_SECONDS"),
    )
    cli_config_path: str = Field(
        default="~/.config/dj-panel/config.json",
        validation_alias=AliasChoices("DJ_PANEL_CLI_CONFIG_PATH"),
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def default_dj_command(self) -> str:
        return f"{self.dj_bin} {self.dj_config_arg} recipe.yaml"

    @property
    def worker_workdir_path(self) -> Path:
        return Path(self.worker_workdir).expanduser()

    @property
    def web_dir_path(self) -> Path:
        if self.web_dir:
            return Path(self.web_dir).expanduser()
        return Path(__file__).resolve().parents[2] / "dj-panel-web"

    @property
    def cli_config_path_obj(self) -> Path:
        return Path(self.cli_config_path).expanduser()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
