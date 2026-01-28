# todo: reimplement the cli with the typer library
"""HireME CLI - Job and Resume Agents.
Provides command-line interfaces for job extraction and resume generation.
"""

import logging
from time import time

import typer

# Lazy-loaded globals
_logger = None
_initialized = False


def _initialize_instrumentation():
    """Initialize logging, telemetry and agent instrumentation lazily."""
    global _initialized, _logger
    if _initialized:
        return

    import logfire
    import structlog
    from pydantic_ai.agent import Agent

    # Configure logfire and instrument agents
    logfire.configure()
    logfire.instrument_pydantic_ai()
    Agent.instrument_all()

    # Configure structlog
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
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    _logger = structlog.get_logger(logger_name=__name__)
    _logger.debug("Structlog configured for HireME CLI.")
    _initialized = True


def get_logger():
    """Get the CLI logger, initializing if needed."""
    global _logger
    if _logger is None:
        import structlog

        _logger = structlog.get_logger(logger_name=__name__)
    return _logger


def main() -> None:
    """CLI for the HireME application."""
    t = time()

    # Initialize instrumentation only when actually running commands
    _initialize_instrumentation()

    # Lazy import command modules to avoid heavy dependency loading at startup
    from hireme.cli.commands.db_cli import app as db_cli
    from hireme.cli.commands.job_agent_cli import app as job_cli
    from hireme.cli.commands.profile import app as profile_cli
    from hireme.cli.commands.resume_agent_cli import app as resume_cli

    app = typer.Typer(
        name="hireme_cli",
        help="HireME CLI - Job and Resume Agents",
        no_args_is_help=True,
    )
    app.add_typer(resume_cli, name="resume")
    app.add_typer(job_cli, name="job")
    app.add_typer(profile_cli, name="profile")
    app.add_typer(db_cli, name="db")

    logger = get_logger()
    logger.info("HireME CLI initialized", duration=time() - t)

    app()

    print(f"Done in {time() - t:.2f} seconds.")
    logger.info("HireME CLI finished", duration=time() - t)


# if __name__ == "__main__":
#     """CLI for the HireME application."""
#     main()
