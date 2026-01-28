# todo: reimplement the cli with the typer library
"""HireME CLI - Job and Resume Agents.
Provides command-line interfaces for job extraction and resume generation.
"""

import logging
from time import time

import logfire
import structlog
import typer

# from langfuse import get_client
from pydantic_ai.agent import Agent

from hireme.cli.commands.db_cli import app as db_cli
from hireme.cli.commands.job_agent_cli import app as job_cli
from hireme.cli.commands.profile import app as profile_cli
from hireme.cli.commands.resume_agent_cli import app as resume_cli

logfire.configure()
logfire.instrument_pydantic_ai()

# langfuse = get_client()

# # Verify connection
# if langfuse.auth_check():
#     print("Langfuse client is authenticated and ready!")
# else:
#     print("Authentication failed. Please check your credentials and host.")

Agent.instrument_all()


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
    # wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger(logger_name=__name__)
logger.debug("Structlog configured for HireME CLI.")
# t = time()


def main() -> None:
    # if __name__ == "__main__":
    """CLI for the HireME application."""
    t = time()
    # typer.run(app)
    app = typer.Typer(
        name="hireme_cli",
        help="HireME CLI - Job and Resume Agents",
        no_args_is_help=True,
    )
    app.add_typer(resume_cli, name="resume")
    app.add_typer(job_cli, name="job")
    app.add_typer(profile_cli, name="profile")
    app.add_typer(db_cli, name="db")
    logger.info("HireME CLI finished", duration=time() - t)
    # typer.run()
    app()
    print(f"Done in {time() - t:.2f} seconds.")
    logger.info("HireME CLI finished", duration=time() - t)


# if __name__ == "__main__":
#     """CLI for the HireME application."""
#     main()
