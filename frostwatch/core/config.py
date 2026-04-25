from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrostWatchConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FROSTWATCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: SecretStr = SecretStr("")
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_database: str = "SNOWFLAKE"
    snowflake_schema: str = "ACCOUNT_USAGE"
    snowflake_role: str = ""

    llm_provider: Literal["anthropic", "openai", "gemini", "ollama"] = "anthropic"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "http://localhost:11434"

    slack_webhook_url: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: SecretStr = SecretStr("")
    email_recipients: list[str] = []

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    credits_per_dollar: float = 3.0
    schedule_cron: str = "0 8 * * 1"
    sync_cron: str = "0 */6 * * *"
    snowflake_query_limit: int = 500
    alert_threshold_multiplier: float = 3.0

    data_dir: Path = Path("~/.frostwatch").expanduser()
    db_path: Path = Path("")

    @model_validator(mode="after")
    def set_db_path(self) -> FrostWatchConfig:
        if not self.db_path or str(self.db_path) == "":
            self.db_path = self.data_dir / "frostwatch.db"
        return self

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, v: str | Path) -> Path:
        return Path(v).expanduser()


def load_config(config_path: Path | None = None) -> FrostWatchConfig:
    if config_path is None:
        config_path = Path("~/.frostwatch/config.yaml").expanduser()

    yaml_data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f)
            if isinstance(raw, dict):
                yaml_data = raw

    env_overrides: dict = {}
    for key in FrostWatchConfig.model_fields:
        env_key = f"FROSTWATCH_{key.upper()}"
        if env_key in os.environ:
            env_overrides[key] = os.environ[env_key]

    merged = {**yaml_data, **env_overrides}
    config = FrostWatchConfig(**merged)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    return config


def save_config(config: FrostWatchConfig, path: Path | None = None) -> None:
    if path is None:
        path = Path("~/.frostwatch/config.yaml").expanduser()

    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(
        exclude={"db_path"},
        mode="json",
    )

    for secret_field in ("snowflake_password", "llm_api_key", "email_smtp_password"):
        if secret_field in data and isinstance(data[secret_field], dict):
            data[secret_field] = data[secret_field].get("secret_value", "")

    data["data_dir"] = str(data["data_dir"])

    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=True)
