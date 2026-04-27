from __future__ import annotations

import contextlib
import json
import smtplib

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from frostwatch.api.models import SettingsResponse, SettingsUpdate
from frostwatch.core.config import FrostWatchConfig
from frostwatch.core.db import SettingsStore, get_db
from frostwatch.llm.factory import get_llm_provider

router = APIRouter()


def _config_to_response(config: FrostWatchConfig) -> SettingsResponse:
    return SettingsResponse(
        llm_provider=config.llm_provider,
        llm_model=config.llm_model,
        llm_base_url=config.llm_base_url,
        snowflake_account=config.snowflake_account,
        snowflake_user=config.snowflake_user,
        snowflake_warehouse=config.snowflake_warehouse,
        snowflake_database=config.snowflake_database,
        snowflake_role=config.snowflake_role,
        slack_webhook_url_set=bool(config.slack_webhook_url),
        email_recipients=config.email_recipients,
        credits_per_dollar=config.credits_per_dollar,
        schedule_cron=config.schedule_cron,
        sync_cron=config.sync_cron,
        snowflake_query_limit=config.snowflake_query_limit,
        alert_threshold_multiplier=config.alert_threshold_multiplier,
        llm_api_key_set=bool(config.llm_api_key.get_secret_value()),
        snowflake_password_set=bool(config.snowflake_password.get_secret_value()),
        email_smtp_host=config.email_smtp_host,
        email_smtp_port=config.email_smtp_port,
        email_smtp_user=config.email_smtp_user,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(request: Request) -> SettingsResponse:
    return _config_to_response(request.app.state.config)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    request: Request,
    update: SettingsUpdate,
) -> SettingsResponse:
    app = request.app
    current_config = app.state.config

    current_data = current_config.model_dump(mode="json")
    for secret_field in ("snowflake_password", "llm_api_key", "email_smtp_password"):
        if secret_field in current_data and isinstance(current_data[secret_field], dict):
            current_data[secret_field] = current_data[secret_field].get("secret_value", "")

    updates = update.model_dump(exclude_none=True)
    current_data.update(updates)
    current_data.pop("db_path", None)

    if "data_dir" in current_data:
        current_data["data_dir"] = str(current_data["data_dir"])

    try:
        new_config = FrostWatchConfig(**current_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        async with get_db() as session:
            for key, value in updates.items():
                stmt = sqlite_insert(SettingsStore).values(key=key, value=json.dumps(value))
                stmt = stmt.on_conflict_do_update(
                    index_elements=["key"], set_={"value": json.dumps(value)}
                )
                await session.execute(stmt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist settings: {exc}") from exc

    app.state.config = new_config
    with contextlib.suppress(Exception):
        app.state.llm_provider = get_llm_provider(new_config)

    return _config_to_response(new_config)


@router.post("/settings/test-snowflake")
async def test_snowflake_connection(request: Request) -> dict:
    from frostwatch.snowflake.client import SnowflakeClient

    config = request.app.state.config
    if not config.snowflake_account or not config.snowflake_user:
        raise HTTPException(status_code=400, detail="Snowflake account and user are required")

    try:
        client = SnowflakeClient(config)
        await client.execute("SELECT 1 AS ping", {})
        return {"status": "ok", "message": "Connection successful"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc


@router.post("/settings/test-email")
async def test_email_connection(request: Request) -> dict:
    config = request.app.state.config
    if not config.email_smtp_host:
        raise HTTPException(status_code=400, detail="SMTP host is not configured")

    try:
        with smtplib.SMTP(config.email_smtp_host, config.email_smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if config.email_smtp_port == 587:
                smtp.starttls()
            if config.email_smtp_user and config.email_smtp_password.get_secret_value():
                smtp.login(
                    config.email_smtp_user,
                    config.email_smtp_password.get_secret_value(),
                )
        return {"status": "ok", "message": "SMTP connection successful"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"SMTP connection failed: {exc}") from exc
