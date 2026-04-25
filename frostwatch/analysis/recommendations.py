from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frostwatch.llm.base import LLMProvider
    from frostwatch.analysis.cost import CostBreakdown

SYSTEM_PROMPT = """You are FrostWatch, an AI assistant specializing in Snowflake cost optimization and query performance analysis.
Your role is to:
1. Explain cost anomalies in plain English so non-technical stakeholders can understand them.
2. Suggest concrete, actionable query rewrites to reduce credit consumption.
3. Recommend warehouse sizing changes based on usage patterns.

Be concise, specific, and prioritize high-impact recommendations. Use dollar amounts and percentages where available."""


def build_llm_prompt(
    queries: list[dict],
    anomalies: list[dict],
    cost_breakdown: "CostBreakdown",
    period_days: int,
) -> str:
    lines: list[str] = []

    lines.append(f"## FrostWatch Analysis Report — Last {period_days} Days\n")

    lines.append("### Cost Summary")
    lines.append(f"- Total credits used: {cost_breakdown.total_credits:.2f}")
    lines.append(f"- Total cost: ${cost_breakdown.total_cost_usd:.2f}")
    lines.append("")

    if cost_breakdown.by_warehouse:
        lines.append("### Top Warehouses by Cost")
        for item in cost_breakdown.by_warehouse[:5]:
            lines.append(
                f"- {item.name}: {item.credits:.2f} credits (${item.cost_usd:.2f}, {item.pct_of_total:.1f}%)"
            )
        lines.append("")

    if cost_breakdown.by_user:
        lines.append("### Top Users by Credits Consumed")
        for item in cost_breakdown.by_user[:5]:
            lines.append(
                f"- {item.name}: {item.credits:.2f} credits (${item.cost_usd:.2f})"
            )
        lines.append("")

    if anomalies:
        lines.append("### Detected Anomalies")
        for a in anomalies[:10]:
            wh = a.get("warehouse_name", "unknown")
            atype = a.get("anomaly_type", "unknown")
            severity = a.get("severity", "unknown")
            description = a.get("description", "")
            factor = a.get("spike_factor", 0)
            lines.append(
                f"- [{severity.upper()}] {wh} — {atype} (spike factor: {factor:.1f}x): {description}"
            )
        lines.append("")

    if queries:
        lines.append("### Top 10 Most Expensive Queries")
        top_queries = sorted(
            queries, key=lambda q: float(q.get("credits_used") or 0), reverse=True
        )[:10]
        for i, q in enumerate(top_queries, 1):
            credits = float(q.get("credits_used") or 0)
            exec_ms = float(q.get("execution_time_ms") or 0)
            user = q.get("user_name", "unknown")
            wh = q.get("warehouse_name", "unknown")
            text = (q.get("query_text") or "")[:500]
            lines.append(f"\n**Query {i}** — {credits:.4f} credits, {exec_ms/1000:.1f}s, user={user}, warehouse={wh}")
            lines.append(f"```sql\n{text}\n```")
        lines.append("")

    lines.append("## Your Analysis Tasks")
    lines.append(
        "1. **Anomaly Explanation**: For each anomaly listed above, explain in plain English what likely caused it and what business impact it may have."
    )
    lines.append(
        "2. **Top 3 Query Rewrites**: Select the 3 most expensive queries above and suggest specific SQL rewrites or optimizations that would reduce their credit consumption."
    )
    lines.append(
        "3. **Warehouse Right-Sizing**: Based on the warehouse usage patterns, recommend specific warehouses that should be upsized, downsized, or have auto-suspend tuned."
    )
    lines.append(
        "4. **Quick Wins**: List 2-3 immediate actions the team can take to reduce costs this week."
    )

    return "\n".join(lines)


async def generate_report(
    llm: "LLMProvider",
    queries: list[dict],
    anomalies: list[dict],
    cost_breakdown: "CostBreakdown",
    period_days: int = 7,
) -> str:
    prompt = build_llm_prompt(queries, anomalies, cost_breakdown, period_days)
    return await llm.complete(prompt, system=SYSTEM_PROMPT)
