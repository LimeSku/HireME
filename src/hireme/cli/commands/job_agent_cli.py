from typing import Literal

from hireme.agents.job_agent import main


def run_agent(
    job: str,
    max_results_per_source: int,
    location: str,
    mode: Literal["testing", "scrapper"],
    export_path: str | None,
):
    """CLI for the Job Extraction Agent."""
    import asyncio

    asyncio.run(
        main(
            mode=mode,
            export_path=export_path,
            query=job,
            location=location,
            max_results_per_source=max_results_per_source,
        )
    )
