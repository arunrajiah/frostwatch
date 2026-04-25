from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from frostwatch import __version__

app = typer.Typer(
    name="frostwatch",
    help="FrostWatch — AI-powered Snowflake cost & query observability",
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
def version() -> None:
    """Print FrostWatch version."""
    console.print(f"FrostWatch v{__version__}")


if __name__ == "__main__":
    app()
