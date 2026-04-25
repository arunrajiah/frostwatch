from __future__ import annotations

import httpx


async def send_slack_digest(
    webhook_url: str,
    report_text: str,
    cost_summary: dict,
) -> None:
    total_credits = cost_summary.get("total_credits_7d", 0)
    total_cost = cost_summary.get("total_cost_usd_7d", 0)

    preview = report_text[:2800] + ("..." if len(report_text) > 2800 else "")

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "FrostWatch Weekly Snowflake Report",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Credits Used (7d):*\n{total_credits:.2f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Estimated Cost (7d):*\n${total_cost:.2f}",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": preview},
            },
        ]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
