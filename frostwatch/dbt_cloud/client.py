"""Async client for the dbt Cloud REST API (v2).

Only the endpoints FrostWatch needs are implemented:
  - GET /api/v2/accounts/{account_id}/runs/
  - GET /api/v2/accounts/{account_id}/jobs/
  - GET /api/v2/accounts/{account_id}/environments/
  - GET /api/v2/accounts/{account_id}/projects/
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

_DEFAULT_BASE_URL = "https://cloud.getdbt.com"
_TIMEOUT = 30.0
_PAGE_SIZE = 100


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string from the dbt Cloud API."""
    if not value:
        return None
    try:
        # dbt Cloud returns strings like "2026-05-01 10:23:45.123456+00:00"
        return datetime.fromisoformat(value.replace(" ", "T"))
    except (ValueError, AttributeError):
        return None


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class DbtCloudClient:
    """Thin async wrapper around the dbt Cloud REST API v2."""

    def __init__(
        self,
        account_id: str,
        api_token: str,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self.account_id = str(account_id)
        self._headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        }
        self._base = base_url.rstrip("/")

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_all(self, path: str, params: dict | None = None) -> list[dict]:
        """Paginate through a dbt Cloud list endpoint and return all data items."""
        params = dict(params or {})
        params.setdefault("limit", _PAGE_SIZE)
        params["offset"] = 0
        results: list[dict] = []

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            while True:
                resp = await client.get(
                    f"{self._base}{path}",
                    headers=self._headers,
                    params=params,
                )
                resp.raise_for_status()
                body: dict[str, Any] = resp.json()
                data: list[dict] = body.get("data") or []
                results.extend(data)

                extra = body.get("extra") or {}
                pagination = extra.get("pagination") or {}
                total_count = pagination.get("total_count", 0)
                if len(results) >= total_count or len(data) < _PAGE_SIZE:
                    break
                params["offset"] += _PAGE_SIZE

        return results

    def _acct(self, endpoint: str) -> str:
        return f"/api/v2/accounts/{self.account_id}/{endpoint.lstrip('/')}"

    # ── Public methods ────────────────────────────────────────────────────────

    async def get_runs(self, days: int = 30) -> list[dict]:
        """Return dbt Cloud runs from the last *days* days, newest first."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        raw = await self._get_all(self._acct("runs/"), {"order_by": "-id", "include_related": "[]"})

        parsed = []
        for r in raw:
            started = _to_utc(_parse_dt(r.get("started_at")))
            if started and started < cutoff:
                continue
            finished = _to_utc(_parse_dt(r.get("finished_at")))
            duration: float | None = None
            if started and finished:
                duration = (finished - started).total_seconds()

            status_humanized = r.get("status_humanized") or ""
            status = (
                "success"
                if "success" in status_humanized.lower()
                else (
                    "error"
                    if "error" in status_humanized.lower()
                    else (
                        "cancelled"
                        if "cancel" in status_humanized.lower()
                        else status_humanized.lower()
                    )
                )
            )

            parsed.append(
                {
                    "run_id": r.get("id"),
                    "job_id": r.get("job_id"),
                    "job_name": None,  # enriched below if jobs fetched separately
                    "environment_id": r.get("environment_id"),
                    "environment_name": None,
                    "project_id": r.get("project_id"),
                    "project_name": None,
                    "triggered_by": r.get("trigger", {}).get("cause")
                    if r.get("trigger")
                    else ("scheduled" if r.get("is_complete") else "api"),
                    "status": status,
                    "started_at": started,
                    "finished_at": finished,
                    "duration_seconds": duration,
                    "models_executed": (
                        (r.get("run_steps") or [{}])[-1].get("completed_at")
                        and r.get("job", {}).get("execute_steps")
                        and len(r.get("job", {}).get("execute_steps", []))
                    )
                    or None,
                }
            )
        return parsed

    async def get_jobs(self) -> list[dict]:
        """Return all jobs in the account."""
        raw = await self._get_all(self._acct("jobs/"))
        return [
            {
                "job_id": r.get("id"),
                "job_name": r.get("name"),
                "environment_id": r.get("environment_id"),
                "project_id": r.get("project_id"),
                "schedule_type": (r.get("schedule") or {}).get("type"),
                "dbt_version": r.get("dbt_version"),
            }
            for r in raw
        ]

    async def get_environments(self) -> list[dict]:
        """Return all environments in the account."""
        raw = await self._get_all(self._acct("environments/"))
        return [
            {
                "environment_id": r.get("id"),
                "environment_name": r.get("name"),
                "project_id": r.get("project_id"),
                "environment_type": r.get("type"),
                "dbt_version": r.get("dbt_version"),
            }
            for r in raw
        ]

    async def get_projects(self) -> list[dict]:
        """Return all projects in the account."""
        raw = await self._get_all(self._acct("projects/"))
        return [
            {
                "project_id": r.get("id"),
                "project_name": r.get("name"),
            }
            for r in raw
        ]

    async def test_connection(self) -> bool:
        """Return True if credentials are valid; raise on auth error."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base}/api/v2/accounts/{self.account_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()
            return True
