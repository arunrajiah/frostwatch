from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from frostwatch import __version__

app = typer.Typer(
    name="frostwatch",
    help="FrostWatch: find Snowflake savings in 60 seconds (frostwatch audit), then monitor cost and queries",
    add_completion=False,
)
config_app = typer.Typer(help="Manage FrostWatch configuration")
app.add_typer(config_app, name="config")

console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
) -> None:
    """Start the FrostWatch API server."""
    import uvicorn

    console.print(
        f"[bold cyan]FrostWatch v{__version__}[/bold cyan] starting on http://{host}:{port}"
    )
    uvicorn.run(
        "frostwatch.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def sync() -> None:
    """Run a one-off Snowflake data sync (no server required)."""
    from frostwatch.api.routes.sync import run_sync
    from frostwatch.core.config import load_config
    from frostwatch.core.db import init_db
    from frostwatch.snowflake.client import SnowflakeClient

    async def _run():
        config = load_config()
        await init_db(config.db_path)
        client = SnowflakeClient(config)

        console.print("[bold]Testing Snowflake connection...[/bold]")
        ok = await client.test_connection()
        if not ok:
            console.print("[red]Failed to connect to Snowflake. Check your config.[/red]")
            raise typer.Exit(code=1)

        console.print("[green]Connected.[/green] Running sync...")
        await run_sync(config, client)
        console.print("[green]Sync complete.[/green]")

    asyncio.run(_run())


@config_app.command("init")
def config_init(
    path: Path | None = typer.Option(None, "--path", help="Output path for config file"),  # noqa: B008
) -> None:
    """Create a template config file at ~/.frostwatch/config.yaml."""
    import yaml

    target = path or Path("~/.frostwatch/config.yaml").expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)

    example = {
        "snowflake_account": "myorg-myaccount",
        "snowflake_user": "myuser",
        "snowflake_password": "",
        "snowflake_warehouse": "COMPUTE_WH",
        "snowflake_database": "SNOWFLAKE",
        "snowflake_schema": "ACCOUNT_USAGE",
        "snowflake_role": "",
        "llm_provider": "anthropic",
        "llm_model": "",
        "llm_api_key": "",
        "llm_base_url": "http://localhost:11434",
        "slack_webhook_url": "",
        "email_smtp_host": "",
        "email_smtp_port": 587,
        "email_smtp_user": "",
        "email_smtp_password": "",
        "email_recipients": [],
        "credits_per_dollar": 3.0,
        "schedule_cron": "0 8 * * 1",
        "alert_threshold_multiplier": 3.0,
        "data_dir": str(Path("~/.frostwatch").expanduser()),
    }

    if target.exists():
        console.print(f"[yellow]Config already exists at {target}. Not overwriting.[/yellow]")
        raise typer.Exit(code=1)

    with open(target, "w") as f:
        yaml.safe_dump(example, f, default_flow_style=False, sort_keys=True)

    console.print(f"[green]Config written to {target}[/green]")
    console.print("Edit the file to add your Snowflake credentials and LLM API key.")


@config_app.command("show")
def config_show() -> None:
    """Print the current configuration (secrets masked)."""
    from frostwatch.core.config import load_config

    config = load_config()

    table = Table(title="FrostWatch Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    def mask(value: str) -> str:
        if not value:
            return "[dim](not set)[/dim]"
        return "*" * 8 + value[-4:] if len(value) > 4 else "****"

    rows = [
        ("snowflake_account", config.snowflake_account or "(not set)"),
        ("snowflake_user", config.snowflake_user or "(not set)"),
        ("snowflake_password", mask(config.snowflake_password.get_secret_value())),
        ("snowflake_warehouse", config.snowflake_warehouse),
        ("snowflake_database", config.snowflake_database),
        ("snowflake_schema", config.snowflake_schema),
        ("snowflake_role", config.snowflake_role or "(not set)"),
        ("llm_provider", config.llm_provider),
        ("llm_model", config.llm_model or "(default)"),
        ("llm_api_key", mask(config.llm_api_key.get_secret_value())),
        ("llm_base_url", config.llm_base_url),
        (
            "slack_webhook_url",
            mask(config.slack_webhook_url) if config.slack_webhook_url else "(not set)",
        ),
        ("email_smtp_host", config.email_smtp_host or "(not set)"),
        ("email_smtp_port", str(config.email_smtp_port)),
        ("email_smtp_user", config.email_smtp_user or "(not set)"),
        ("email_recipients", ", ".join(config.email_recipients) or "(none)"),
        ("credits_per_dollar", str(config.credits_per_dollar)),
        ("schedule_cron", config.schedule_cron),
        ("alert_threshold_multiplier", str(config.alert_threshold_multiplier)),
        ("data_dir", str(config.data_dir)),
        ("db_path", str(config.db_path)),
    ]

    for key, value in rows:
        table.add_row(key, value)

    console.print(table)


@app.command()
def demo(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    skip_seed: bool = typer.Option(
        False, "--skip-seed", help="Skip seeding and just start the server"
    ),
) -> None:
    """Start FrostWatch with pre-loaded synthetic demo data (no Snowflake needed)."""
    import uvicorn

    from frostwatch.core.config import FrostWatchConfig
    from frostwatch.core.db import init_db

    # Demo data lives in its own database so it never mixes with real synced
    # data, and is rebuilt on each run so reruns don't hit unique constraints.
    demo_db = FrostWatchConfig().data_dir / "demo" / "frostwatch.db"
    if not skip_seed:
        demo_db.unlink(missing_ok=True)
    os.environ["FROSTWATCH_DB_PATH"] = str(demo_db)  # picked up by the API's load_config()

    async def _seed_and_serve() -> None:
        config = FrostWatchConfig()  # defaults — no Snowflake creds required
        await init_db(config.db_path)

        if not skip_seed:
            from frostwatch.demo.seed import seed_demo

            console.print("[bold cyan]Seeding demo data…[/bold cyan]")
            await seed_demo(config)
            console.print("[green]✓ Demo data ready.[/green]")

        console.print(
            f"\n[bold cyan]FrostWatch v{__version__}: DEMO MODE[/bold cyan]\n"
            f"  Dashboard → [link]http://{host}:{port}[/link]\n"
            f"  API docs  → [link]http://{host}:{port}/api/docs[/link]\n"
            "[dim]No Snowflake connection required. Data is entirely synthetic.[/dim]\n"
        )

    asyncio.run(_seed_and_serve())

    uvicorn.run(
        "frostwatch.api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
    )


@app.command()
def audit(
    connection: str = typer.Option(
        "", "--connection", "-c", help="Named connection from ~/.snowflake/connections.toml"
    ),
    account: str = typer.Option("", "--account", "-a", help="Snowflake account identifier"),
    user: str = typer.Option("", "--user", "-u", help="Snowflake user"),
    authenticator: str = typer.Option(
        "", "--authenticator", help="e.g. externalbrowser (SSO), SNOWFLAKE_JWT, oauth"
    ),
    private_key: str = typer.Option("", "--private-key", help="Path to a key-pair .p8 file"),
    role: str = typer.Option("", "--role", "-r", help="Role with ACCOUNT_USAGE access"),
    warehouse: str = typer.Option("", "--warehouse", "-w", help="Warehouse to run the audit on"),
    days: int = typer.Option(30, "--days", "-d", min=7, max=365, help="History window"),
    output_path: str = typer.Option(
        "frostwatch-audit.html", "--output", "-o", help="Report path (.html, .md, .json)"
    ),
    price: float = typer.Option(0.0, "--price", help="USD per credit (default: config or 3.00)"),
    storage_price: float = typer.Option(
        0.0, "--storage-price", help="USD per TB-month of storage (default: config or 23)"
    ),
    demo: bool = typer.Option(False, "--demo", help="Use synthetic data, no Snowflake needed"),
    open_report: bool = typer.Option(
        True, "--open/--no-open", help="Open the HTML report in your browser when done"
    ),
    fail_over: float = typer.Option(
        0.0, "--fail-over", help="Exit 2 if monthly savings exceed this USD amount (for CI)"
    ),
) -> None:
    """Find Snowflake savings in about a minute. No server, no LLM, read-only.

    Writes a shareable report with dollar estimates and the SQL to fix each issue.
    """
    from frostwatch.analysis.advisor import analyze, run_audit
    from frostwatch.analysis.audit_report import render
    from frostwatch.core.config import load_config

    output = Path(output_path)
    fmt = {".md": "md", ".markdown": "md", ".json": "json"}.get(output.suffix.lower(), "html")
    config = load_config()
    if price:
        config.credits_per_dollar = price
    if storage_price:
        config.storage_price_per_tb = storage_price

    if demo:
        from frostwatch.demo.audit_demo import demo_inputs

        result = analyze(
            demo_inputs(),
            days=days,
            credit_price=config.credits_per_dollar,
            storage_price_per_tb=config.storage_price_per_tb,
            account="DEMO_ACCOUNT",
            demo=True,
        )
    else:
        from pydantic import SecretStr

        from frostwatch.snowflake.client import SnowflakeClient

        overrides = {
            "snowflake_connection_name": connection,
            "snowflake_account": account,
            "snowflake_user": user,
            "snowflake_authenticator": authenticator,
            "snowflake_private_key_path": private_key,
            "snowflake_role": role,
            "snowflake_warehouse": warehouse,
        }
        for k, v in overrides.items():
            if v:
                setattr(config, k, v)
        if (
            os.environ.get("SNOWFLAKE_PASSWORD")
            and not config.snowflake_password.get_secret_value()
        ):
            config.snowflake_password = SecretStr(os.environ["SNOWFLAKE_PASSWORD"])
        has_creds = (
            config.snowflake_connection_name
            or config.snowflake_private_key_path
            or config.snowflake_authenticator
            or config.snowflake_password.get_secret_value()
        )
        if not config.snowflake_connection_name and not (
            config.snowflake_account and config.snowflake_user
        ):
            console.print(
                "[red]No Snowflake connection given.[/red] Use one of:\n"
                "  frostwatch audit --connection <name>        "
                "[dim](from ~/.snowflake/connections.toml)[/dim]\n"
                "  frostwatch audit -a <account> -u <user>     [dim](opens SSO in browser)[/dim]\n"
                "  frostwatch audit --demo                     [dim](synthetic data)[/dim]"
            )
            raise typer.Exit(1)
        if not has_creds:
            config.snowflake_authenticator = "externalbrowser"
            console.print("[dim]No password or key given, using browser SSO.[/dim]")

        client = SnowflakeClient(config)

        async def _run():
            with console.status("Connecting to Snowflake...") as status:
                ok, err = await client.test_connection_detail()
                if not ok:
                    console.print(f"[red]✗ {err}[/red]")
                    raise typer.Exit(1)

                def step(key: str) -> None:
                    status.update(f"Auditing: {key.replace('_', ' ')}...")

                return await run_audit(client, config, days=days, on_step=step)

        try:
            result = asyncio.run(_run())
        finally:
            client.close()
        if not result.account:
            result.account = config.snowflake_connection_name or config.snowflake_account

    output.write_text(render(result, fmt), encoding="utf-8")
    _print_audit_summary(result)
    console.print(f"\n[green]✓ Report written to[/green] [bold]{output.resolve()}[/bold]")
    if result.skipped:
        console.print(
            f"[yellow]{len(result.skipped)} dataset(s) skipped (see report). Most often the "
            "role needs: GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE <role>;[/yellow]"
        )
    console.print(
        "[dim]Keep watching continuously: frostwatch serve  |  "
        "Star us: https://github.com/arunrajiah/frostwatch[/dim]"
    )
    if fmt == "html" and open_report:
        import webbrowser

        webbrowser.open(output.resolve().as_uri())
    if fail_over and result.monthly_savings_usd > fail_over:
        raise typer.Exit(2)


def _print_audit_summary(result) -> None:
    def money(v: float) -> str:
        return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"

    colors = {"high": "red", "medium": "yellow", "low": "blue", "info": "dim"}
    table = Table(title="Savings Advisor", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Severity")
    table.add_column("Finding")
    table.add_column("Object", overflow="fold", max_width=40)
    table.add_column("Save / mo", justify="right", style="green")
    for i, f in enumerate(result.findings, 1):
        table.add_row(
            str(i),
            f"[{colors[f.severity]}]{f.severity}[/]",
            f.title,
            f.object_name,
            money(f.monthly_savings_usd) if f.monthly_savings_usd else "[dim]risk[/dim]",
        )
    console.print(table)
    console.print(
        f"\n[bold green]Estimated savings: {money(result.monthly_savings_usd)}/month "
        f"({money(result.annual_savings_usd)}/year)[/bold green] on "
        f"{money(result.monthly_compute_spend_usd)}/month of warehouse compute"
        + (" [yellow](demo data)[/yellow]" if result.demo else "")
    )


@app.command()
def version() -> None:
    """Print FrostWatch version."""
    console.print(f"FrostWatch v{__version__}")


if __name__ == "__main__":
    app()
