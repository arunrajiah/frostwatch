from __future__ import annotations

import asyncio
import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, Any

import snowflake.connector

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="snowflake")


def build_connect_kwargs(config: FrostWatchConfig) -> dict[str, Any]:
    """Translate FrostWatch config into snowflake.connector.connect() kwargs.

    Supports, in priority order: a named connection from
    ~/.snowflake/connections.toml, key-pair auth, an explicit authenticator
    (externalbrowser SSO, oauth, MFA), and finally plain password.
    """
    kwargs: dict[str, Any] = {"login_timeout": 60, "network_timeout": 120}
    name = getattr(config, "snowflake_connection_name", "")
    if name:
        kwargs["connection_name"] = name
    else:
        kwargs["account"] = config.snowflake_account
        kwargs["user"] = config.snowflake_user

    key_path = getattr(config, "snowflake_private_key_path", "")
    authenticator = getattr(config, "snowflake_authenticator", "")
    password = config.snowflake_password.get_secret_value()
    if key_path:
        kwargs["private_key_file"] = key_path
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        passphrase = config.snowflake_private_key_passphrase.get_secret_value()
        if passphrase:
            kwargs["private_key_file_pwd"] = passphrase
    elif authenticator:
        kwargs["authenticator"] = authenticator
        if password and authenticator.lower() != "externalbrowser":
            kwargs["password"] = password
    elif password:
        kwargs["password"] = password

    if authenticator.lower() == "externalbrowser":
        # Cache the SSO token so the browser opens once, not per query.
        kwargs["client_store_temporary_credential"] = True

    # Explicit values override the named connection only when set.
    for opt in ("warehouse", "role"):
        val = getattr(config, f"snowflake_{opt}", "")
        if val and not (name and opt == "warehouse" and val == "COMPUTE_WH"):
            kwargs[opt] = val
    if not name:
        kwargs["database"] = config.snowflake_database
        kwargs["schema"] = config.snowflake_schema
    return kwargs


class SnowflakeClient:
    """Async wrapper around one reused Snowflake connection.

    The connection is reused across queries (one SSO prompt, one login) and
    transparently re-opened if the session expired.
    """

    def __init__(self, config: FrostWatchConfig) -> None:
        self._config = config
        self._conn: snowflake.connector.SnowflakeConnection | None = None
        self._lock = threading.Lock()

    def _connect(self) -> snowflake.connector.SnowflakeConnection:
        try:
            return snowflake.connector.connect(**build_connect_kwargs(self._config))
        except snowflake.connector.errors.DatabaseError as exc:
            raise ConnectionError(
                f"Snowflake connection failed: {exc}. Check your account, user, credentials, "
                "warehouse, and role. Password-only logins may be blocked by MFA: try "
                "authenticator 'externalbrowser', key-pair auth, or a connections.toml entry."
            ) from exc
        except Exception as exc:
            raise ConnectionError(f"Snowflake connection error: {exc}") from exc

    def _get_connection(self) -> snowflake.connector.SnowflakeConnection:
        with self._lock:
            if self._conn is None or self._conn.is_closed():
                self._conn = self._connect()
            return self._conn

    def _reset(self) -> None:
        with self._lock:
            if self._conn is not None:
                with contextlib.suppress(Exception):
                    self._conn.close()
            self._conn = None

    def _execute_sync(self, sql: str, params: dict | None) -> list[dict]:
        for attempt in (1, 2):
            conn = self._get_connection()
            try:
                cursor = conn.cursor(snowflake.connector.DictCursor)
                try:
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    return cursor.fetchall()
                finally:
                    cursor.close()
            except snowflake.connector.errors.ProgrammingError:
                raise  # SQL / privilege error: retrying won't help
            except (snowflake.connector.errors.OperationalError, OSError):
                self._reset()
                if attempt == 2:
                    raise
        return []

    async def execute(self, sql: str, params: dict | None = None) -> list[dict]:
        loop = asyncio.get_running_loop()
        fn = partial(self._execute_sync, sql, params)
        return await loop.run_in_executor(_executor, fn)

    def _test_connection_sync(self) -> bool:
        try:
            self._execute_sync("SELECT 1", None)
            return True
        except Exception:
            return False

    async def test_connection(self) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._test_connection_sync)

    async def test_connection_detail(self) -> tuple[bool, str]:
        """Like test_connection, but returns the error message on failure."""
        loop = asyncio.get_running_loop()

        def _run() -> tuple[bool, str]:
            try:
                self._execute_sync("SELECT 1", None)
                return True, ""
            except Exception as exc:
                return False, str(exc)

        return await loop.run_in_executor(_executor, _run)

    def close(self) -> None:
        self._reset()
