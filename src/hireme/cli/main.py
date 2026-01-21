# todo: reimplement the cli with the typer library
"""HireME CLI - Job and Resume Agents.
Provides command-line interfaces for job extraction and resume generation.
"""

import logging

import logfire
import structlog
import typer

import hireme.cli.commands.resume_agent_cli as resume_cli
from hireme.cli.commands.job_agent_cli import app as job_cli

logfire.configure()
logfire.instrument_pydantic_ai()
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)
logger = structlog.get_logger(logger_name=__name__)
logger.debug("Structlog configured for HireME CLI.")


app = typer.Typer(name="hireme_cli", help="HireME CLI - Job and Resume Agents")
app.add_typer(resume_cli.app, name="resume")
app.add_typer(job_cli, name="job")


def main() -> None:
    """CLI for the HireME application."""

    app()


if __name__ == "__main__":
    """CLI for the HireME application."""
    main()
