from __future__ import annotations

import asyncio
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")


def _send_sync(config: "FrostWatchConfig", report_text: str, cost_summary: dict) -> None:
    total_credits = cost_summary.get("total_credits_7d", 0)
    total_cost = cost_summary.get("total_cost_usd_7d", 0)

    subject = f"FrostWatch Weekly Report — {total_credits:.2f} credits / ${total_cost:.2f}"

    html_body = f"""
<html>
<body style="font-family: sans-serif; max-width: 800px; margin: auto;">
  <h1 style="color: #1e3a5f;">FrostWatch Weekly Snowflake Report</h1>
  <table style="border-collapse: collapse; width: 100%; margin-bottom: 24px;">
    <tr>
      <td style="padding: 12px; background: #f0f4f8; border-radius: 4px;">
        <strong>Credits Used (7d)</strong><br/>{total_credits:.2f}
      </td>
      <td style="padding: 12px; background: #f0f4f8; border-radius: 4px;">
        <strong>Estimated Cost (7d)</strong><br/>${total_cost:.2f}
      </td>
    </tr>
  </table>
  <hr/>
  <pre style="background: #f8f9fa; padding: 16px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word;">{report_text}</pre>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.email_smtp_user
    msg["To"] = ", ".join(config.email_recipients)

    msg.attach(MIMEText(report_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    password = config.email_smtp_password.get_secret_value()

    with smtplib.SMTP(config.email_smtp_host, config.email_smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(config.email_smtp_user, password)
        server.sendmail(
            config.email_smtp_user,
            config.email_recipients,
            msg.as_string(),
        )


async def send_email_digest(
    config: "FrostWatchConfig",
    report_text: str,
    cost_summary: dict,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _executor, _send_sync, config, report_text, cost_summary
    )
