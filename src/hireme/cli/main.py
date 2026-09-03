"""HireME command-line interface."""

import logging
from typing import Annotated

import structlog
import typer

from hireme.cli.commands.db_cli import app as db_cli
from hireme.cli.commands.job_agent_cli import app as job_cli
from hireme.cli.commands.profile import app as profile_cli
from hireme.cli.commands.resume_agent_cli import app as resume_cli
from hireme.cli.commands.run_cli import app as run_cli
from hireme.config import cfg

app = typer.Typer(
    name="hireme", help="HireME job and resume assistant", no_args_is_help=True
)
app.add_typer(resume_cli, name="resume")
app.add_typer(job_cli, name="job")
app.add_typer(profile_cli, name="profile")
app.add_typer(db_cli, name="db")
app.add_typer(run_cli, name="run")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else getattr(logging, cfg.log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if cfg.logfire_enabled:
        import logfire
        from pydantic_ai import Agent
        from pydantic_ai.models.instrumented import InstrumentationSettings

        logfire.configure(send_to_logfire=True, console=False)
        Agent.instrument_all(
            InstrumentationSettings(include_content=cfg.logfire_include_content)
        )


@app.callback()
def cli_callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging."),
    ] = False,
) -> None:
    _configure_logging(verbose)


def main() -> None:
    app()
