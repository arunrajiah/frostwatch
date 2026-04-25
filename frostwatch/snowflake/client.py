from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, Any

import snowflake.connector

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="snowflake")


class SnowflakeClient:
    def __init__(self, config: "FrostWatchConfig") -> None:
        self._config = config

    def _get_connection(self) -> snowflake.connector.SnowflakeConnection:
        password = self._config.snowflake_password.get_secret_value()
        kwargs: dict[str, Any] = {
            "account": self._config.snowflake_account,
            "user": self._config.snowflake_user,
            "password": password,
            "warehouse": self._config.snowflake_warehouse,
            "database": self._config.snowflake_database,
            "schema": self._config.snowflake_schema,
        }
        if self._config.snowflake_role:
            kwargs["role"] = self._config.snowflake_role
        return snowflake.connector.connect(**kwargs)

    def _execute_sync(self, sql: str, params: dict | None) -> list[dict]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor(snowflake.connector.DictCursor)
            cursor.execute(sql, params or {})
            return cursor.fetchall()
        finally:
            conn.close()

    async def execute(self, sql: str, params: dict | None = None) -> list[dict]:
        loop = asyncio.get_running_loop()
        fn = partial(self._execute_sync, sql, params)
        return await loop.run_in_executor(_executor, fn)

    def _test_connection_sync(self) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False

    async def test_connection(self) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._test_connection_sync)
