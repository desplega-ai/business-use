import logging

import click
from alembic import command
from alembic.config import Config as AlembicConfig

from src.logging import configure_logging

log = logging.getLogger(__name__)


configure_logging()


def get_alembic_config() -> AlembicConfig:
    """Get Alembic configuration."""
    alembic_cfg = AlembicConfig("alembic.ini")
    return alembic_cfg


@click.group()
def cli() -> None:
    """Magic CLI - Database management and utilities."""
    pass


@cli.group()
def db() -> None:
    """Database migration commands."""
    pass


@db.command()
@click.argument("revision", default="head")
def migrate(revision: str) -> None:
    """Run database migrations (upgrade to a later version).

    Examples:
        cli db migrate           # Upgrade to latest
        cli db migrate head      # Upgrade to latest
        cli db migrate +1        # Upgrade one version
        cli db migrate ae1027a6  # Upgrade to specific revision
    """
    click.echo(f"Running migrations to: {revision}")
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)
    click.echo("✓ Migrations completed successfully")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI server in development mode.

    Examples:
        cli serve                    # Run on default port 13370
        cli serve --port 8000        # Run on custom port
        cli serve --reload           # Run with auto-reload for development
    """
    import uvicorn

    click.echo(f"Starting API server on {host}:{port}")
    if reload:
        click.echo("Auto-reload enabled")

    uvicorn.run(
        "src.api.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=13370, help="Port to bind to")
@click.option("--workers", default=4, help="Number of worker processes")
def prod(host: str, port: int, workers: int) -> None:
    """Run the FastAPI server in production mode with multiple workers.

    Examples:
        cli prod                     # Run on default port 13370 with 4 workers
        cli prod --port 8000         # Run on custom port
        cli prod --workers 8         # Run with 8 worker processes
    """
    import uvicorn

    click.echo(f"Starting API server in production mode on {host}:{port}")
    click.echo(f"Workers: {workers}")

    uvicorn.run(
        "src.api.api:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
    )


def main() -> None:
    """Entry point for the CLI."""
    log.info("CLI is running")
    cli()


if __name__ == "__main__":
    log.info("Hi there!")
    main()
