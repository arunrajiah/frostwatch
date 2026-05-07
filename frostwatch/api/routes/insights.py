"""v0.2 query deep-dive endpoints.

Routes
------
GET  /api/insights/fingerprints   — Top query patterns by total credits
GET  /api/insights/regressions    — Patterns that regressed week-over-week
GET  /api/insights/forecasts      — Per-warehouse cost projections (7-day)
GET  /api/insights/pruning        — Patterns with poor partition pruning efficiency
POST /api/insights/rewrites       — Request an AI rewrite for a query
GET  /api/insights/rewrites/{id}  — Fetch a previously generated rewrite
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from frostwatch.analysis.fingerprint import build_fingerprints, detect_regressions
from frostwatch.analysis.forecast import forecast_warehouse_costs
from frostwatch.analysis.pruning import detect_poor_pruning
from frostwatch.api.models import (
    CostForecastPoint,
    PartitionPruningRecord,
    QueryFingerprintRecord,
    QueryRegressionRecord,
    QueryRewriteRequest,
    QueryRewriteResponse,
)
from frostwatch.core.db import (
    CachedQuery,
    CachedWarehouseMetric,
    QueryRewrite,
    get_db,
)

router = APIRouter()

# ── Fingerprints ──────────────────────────────────────────────────────────────


@router.get("/insights/fingerprints", response_model=list[QueryFingerprintRecord])
async def get_fingerprints(
    days: int = Query(30, ge=1, le=90, description="Look-back window in days"),
    limit: int = Query(20, ge=1, le=100, description="Max fingerprints to return"),
) -> list[QueryFingerprintRecord]:
    """Return the top query patterns (by total credits) over the last *days* days."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with get_db() as session:
        result = await session.execute(select(CachedQuery).where(CachedQuery.start_time >= cutoff))
        rows = result.scalars().all()

    queries = [
        {c.name: getattr(row, c.name) for c in CachedQuery.__table__.columns} for row in rows
    ]

    fingerprints = build_fingerprints(queries)

    return [QueryFingerprintRecord(**fp) for fp in fingerprints[:limit]]


# ── Regressions ───────────────────────────────────────────────────────────────


@router.get("/insights/regressions", response_model=list[QueryRegressionRecord])
async def get_regressions(
    threshold: float = Query(
        2.0,
        ge=1.1,
        le=20.0,
        description="Min ratio of this-week vs last-week avg credits to flag",
    ),
    limit: int = Query(10, ge=1, le=50),
) -> list[QueryRegressionRecord]:
    """Return query patterns whose average per-execution cost rose this week vs last week."""
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=14)

    async with get_db() as session:
        result = await session.execute(select(CachedQuery).where(CachedQuery.start_time >= cutoff))
        rows = result.scalars().all()

    queries = [
        {c.name: getattr(row, c.name) for c in CachedQuery.__table__.columns} for row in rows
    ]

    regressions = detect_regressions(queries, threshold=threshold, top_n=limit)
    return [QueryRegressionRecord(**r) for r in regressions]


# ── Forecasts ─────────────────────────────────────────────────────────────────


@router.get("/insights/forecasts", response_model=list[CostForecastPoint])
async def get_forecasts(
    request: Request,
    days_ahead: int = Query(7, ge=1, le=30, description="Days to project ahead"),
    history_days: int = Query(30, ge=7, le=90, description="History days to fit"),
) -> list[CostForecastPoint]:
    """Return per-warehouse credit forecasts for the next *days_ahead* days."""
    config = getattr(request.app.state, "config", None)
    credits_per_dollar = getattr(config, "credits_per_dollar", 3.0) if config else 3.0

    async with get_db() as session:
        result = await session.execute(select(CachedWarehouseMetric))
        rows = result.scalars().all()

    metrics = [
        {c.name: getattr(row, c.name) for c in CachedWarehouseMetric.__table__.columns}
        for row in rows
    ]

    forecasts = forecast_warehouse_costs(
        metrics,
        days_ahead=days_ahead,
        history_days=history_days,
        credits_per_dollar=credits_per_dollar,
    )
    return [CostForecastPoint(**f) for f in forecasts]


# ── Partition pruning ─────────────────────────────────────────────────────────


@router.get("/insights/pruning", response_model=list[PartitionPruningRecord])
async def get_pruning(
    days: int = Query(30, ge=1, le=90, description="Look-back window in days"),
    limit: int = Query(20, ge=1, le=100, description="Max patterns to return"),
    min_partitions: int = Query(
        100,
        ge=10,
        description="Min avg partitions_total to include (filters out small tables)",
    ),
    min_ratio: float = Query(
        0.5,
        ge=0.1,
        le=1.0,
        description="Min avg pruning ratio (partitions_scanned / partitions_total) to flag",
    ),
) -> list[PartitionPruningRecord]:
    """Return query patterns with poor partition pruning efficiency.

    Only patterns where ``partitions_total >= min_partitions`` on average are
    included — small tables with few partitions are excluded to avoid noise.
    Results are sorted by impact: pruning_ratio × total_credits × executions.
    """
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with get_db() as session:
        result = await session.execute(select(CachedQuery).where(CachedQuery.start_time >= cutoff))
        rows = result.scalars().all()

    queries = [
        {c.name: getattr(row, c.name) for c in CachedQuery.__table__.columns} for row in rows
    ]

    pruning_issues = detect_poor_pruning(
        queries,
        min_partitions=min_partitions,
        min_ratio=min_ratio,
        top_n=limit,
    )
    return [PartitionPruningRecord(**p) for p in pruning_issues]


# ── Rewrites ──────────────────────────────────────────────────────────────────

_REWRITE_SYSTEM = (
    "You are a Snowflake query optimization expert. "
    "Provide specific, actionable SQL rewrites to reduce Snowflake credit usage. "
    "Be concise and practical — show improved SQL, not just advice."
)


def _build_rewrite_prompt(row: CachedQuery) -> str:
    gb_scanned = f"{(row.bytes_scanned or 0) / 1e9:.2f} GB" if row.bytes_scanned else "unknown"
    return (
        f"Analyze this Snowflake query and suggest optimizations to reduce credit usage.\n\n"
        f"**Query Stats**\n"
        f"- Warehouse: {row.warehouse_name or 'unknown'}\n"
        f"- Credits used: {row.credits_used or 0:.6f}\n"
        f"- Execution time: {int(row.execution_time_ms or 0):,} ms\n"
        f"- Data scanned: {gb_scanned}\n"
        f"- User: {row.user_name or 'unknown'}\n"
        f"- dbt model: {row.dbt_model or 'none'}\n\n"
        f"**SQL**\n```sql\n{row.query_text or ''}\n```\n\n"
        "Provide:\n"
        "## Rewrite\nThe optimized SQL with inline comments explaining the changes.\n\n"
        "## Root Cause\nWhy this query is expensive (1-2 sentences).\n\n"
        "## Recommendations\nClustering keys, filter pushdowns, warehouse right-sizing (bullet list).\n\n"
        "## Estimated Savings\nRough credit reduction as a percentage range."
    )


@router.post("/insights/rewrites", response_model=QueryRewriteResponse)
async def request_rewrite(
    body: QueryRewriteRequest,
    request: Request,
) -> QueryRewriteResponse:
    """Generate an AI-powered rewrite suggestion for the given query_id.

    If a rewrite for this query_id already exists it is returned immediately
    (idempotent). Otherwise the LLM is called and the result is persisted.
    """
    query_id = body.query_id

    # Return cached rewrite if it exists
    async with get_db() as session:
        existing = await session.execute(
            select(QueryRewrite).where(QueryRewrite.query_id == query_id).limit(1)
        )
        cached = existing.scalar_one_or_none()

    if cached is not None:
        return QueryRewriteResponse(
            id=cached.id,
            query_id=cached.query_id,
            fingerprint=cached.fingerprint,
            rewrite_suggestion=cached.rewrite_suggestion or "",
            generated_at=cached.generated_at,
        )

    # Fetch the query
    async with get_db() as session:
        q_result = await session.execute(
            select(CachedQuery).where(CachedQuery.query_id == query_id).limit(1)
        )
        q_row = q_result.scalar_one_or_none()

    if q_row is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")

    # Check LLM is available
    llm = getattr(request.app.state, "llm_provider", None)
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="LLM provider not configured. Set llm_provider and llm_api_key in config.",
        )

    # Build fingerprint for the query
    from frostwatch.analysis.fingerprint import fingerprint_sql

    fp = fingerprint_sql(q_row.query_text or "")

    # Call LLM
    prompt = _build_rewrite_prompt(q_row)
    try:
        suggestion = await llm.complete(prompt, system=_REWRITE_SYSTEM)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    # Persist
    now = datetime.now(UTC)
    async with get_db() as session:
        rewrite = QueryRewrite(
            query_id=query_id,
            fingerprint=fp,
            rewrite_suggestion=suggestion,
            generated_at=now,
        )
        session.add(rewrite)
        await session.flush()
        rewrite_id = rewrite.id

    return QueryRewriteResponse(
        id=rewrite_id,
        query_id=query_id,
        fingerprint=fp,
        rewrite_suggestion=suggestion,
        generated_at=now,
    )


@router.get("/insights/rewrites/{query_id}", response_model=QueryRewriteResponse)
async def get_rewrite(query_id: str) -> QueryRewriteResponse:
    """Fetch the most recent rewrite suggestion for a given query_id."""
    async with get_db() as session:
        result = await session.execute(
            select(QueryRewrite)
            .where(QueryRewrite.query_id == query_id)
            .order_by(QueryRewrite.generated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No rewrite found for query '{query_id}'. POST to /api/insights/rewrites to generate one.",
        )

    return QueryRewriteResponse(
        id=row.id,
        query_id=row.query_id,
        fingerprint=row.fingerprint,
        rewrite_suggestion=row.rewrite_suggestion or "",
        generated_at=row.generated_at,
    )
