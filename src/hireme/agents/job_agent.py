"""Job extraction agent using Pydantic AI.

Extracts structured job information from web pages or text content
to help users prepare quality applications.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from hireme.scrapping.offers_finder import get_job_urls
from hireme.scrapping.offers_parser import get_job_page

# from hireme.utils.providers import ollama_model
from hireme.utils.providers import get_llm_model

logger = structlog.get_logger(logger_name=__name__)

# =============================================================================
# Enums for structured fields
# =============================================================================

URL_PREVIEW = 50


class ContractType(str, Enum):
    """Type of employment contract."""

    CDI = "CDI"
    CDD = "CDD"
    FREELANCE = "Freelance"
    INTERNSHIP = "Internship"
    APPRENTICESHIP = "Apprenticeship"
    PART_TIME = "Part-time"
    FULL_TIME = "Full-time"
    TEMPORARY = "Temporary"
    UNKNOWN = "Unknown"


class ExperienceLevel(str, Enum):
    """Required experience level."""

    JUNIOR = "Junior (0-2 years)"
    MID = "Mid-level (2-5 years)"
    SENIOR = "Senior (5-10 years)"
    LEAD = "Lead/Principal (10+ years)"
    ANY = "Any level"
    UNKNOWN = "Unknown"


class WorkMode(str, Enum):
    """Work arrangement mode."""

    ONSITE = "On-site"
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    UNKNOWN = "Unknown"


# =============================================================================
# Job Models
# =============================================================================


class Salary(BaseModel):
    """Salary information."""

    min_amount: int | None = Field(None, description="Minimum salary amount")
    max_amount: int | None = Field(None, description="Maximum salary amount")
    currency: str = Field("EUR", description="Currency code (EUR, USD, GBP...)")
    period: Literal["yearly", "monthly", "daily", "hourly"] = Field("yearly")
    is_gross: bool = Field(True, description="True if gross salary, False if net")


class RequiredSkill(BaseModel):
    """A required or preferred skill."""

    name: str = Field(..., description="Skill name (e.g., Python, React, SQL)")
    level: Literal["required", "preferred", "nice-to-have"] = Field("required")
    years_experience: int | None = Field(None, description="Years of experience needed")


class CompanyInfo(BaseModel):
    """Information about the hiring company."""

    name: str = Field(..., description="Company name")
    industry: str | None = Field(None, description="Industry sector")
    size: str | None = Field(
        None, description="Company size (e.g., '50-200 employees', 'Startup')"
    )
    description: str | None = Field(None, description="Brief company description")
    culture_keywords: list[str] = Field(
        default_factory=list, description="Culture/values keywords"
    )


class JobDetails(BaseModel):
    """Complete structured job posting details."""

    # Basic info
    title: str = Field(..., description="Job title")
    company: CompanyInfo
    location: str = Field(..., description="Job location (city, country)")
    work_mode: WorkMode = Field(WorkMode.UNKNOWN)

    # Contract details
    contract_type: list[ContractType] = Field([ContractType.UNKNOWN])
    experience_level: ExperienceLevel = Field(ExperienceLevel.UNKNOWN)
    start_date: str | None = Field(None, description="Expected start date or 'ASAP'")

    # Compensation
    salary: Salary | None = Field(None)
    benefits: list[str] = Field(default_factory=list, description="Listed benefits")

    # Requirements
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    required_languages: list[str] = Field(
        default_factory=list, description="Required spoken languages"
    )
    required_education: str | None = Field(
        None, description="Required education level or degree"
    )

    # Role details
    responsibilities: list[str] = Field(
        default_factory=list, description="Key responsibilities"
    )
    team_info: str | None = Field(None, description="Team size/structure info")
    reports_to: str | None = Field(None, description="Who the role reports to")

    # Application info
    application_deadline: str | None = Field(None)
    application_url: str | None = Field(None)
    contact_email: str | None = Field(None)

    # AI-generated insights
    key_selling_points: list[str] = Field(
        default_factory=list, description="Key points to highlight in your application"
    )
    potential_challenges: list[str] = Field(
        default_factory=list,
        description="Potential challenges or concerns about the role",
    )


class ExtractionFailed(BaseModel):
    """When job extraction fails."""

    reason: str = Field(..., description="Why extraction failed")


# =============================================================================
# Agent Definition
# =============================================================================


old_sys_prompt = """You are an expert job posting analyzer. Your task is to extract 
structured information from job postings to help candidates prepare quality applications.

Guidelines:
- Extract ALL available information from the text
- Use "Unknown" enums when information is not clearly stated
- For skills, distinguish between "required", "preferred", and "nice-to-have"
- Identify key selling points that a candidate should emphasize in their application
- Note any potential red flags or challenges about the role
- Be precise with salary information (currency, gross/net, period)
- Extract company culture keywords when mentioned
- If the text is not a job posting, return ExtractionFailed with reason
"""

job_extraction_agent: Agent[None, JobDetails | ExtractionFailed] = Agent(
    model=get_llm_model("mistral-nemo:12b"),
    output_type=JobDetails | ExtractionFailed,
    retries=3,
    # system_prompt=
)


SAMPLE_POSTING = """
    Senior Python Developer - FinTech Startup
    
    About Us:
    We're a fast-growing fintech startup (Series B, 80 employees) revolutionizing 
    payments in Europe. We value innovation, collaboration, and work-life balance.
    
    Location: Paris, France (Hybrid - 2 days remote)
    Contract: CDI (Permanent)
    Salary: 65,000 - 85,000 EUR gross/year + equity
    
    We're looking for a Senior Python Developer to join our Platform team (6 engineers).
    You'll report to the Engineering Manager.
    
    Requirements:
    - 5+ years Python experience (required)
    - FastAPI or Django REST framework (required)
    - PostgreSQL and Redis (required)
    - Kubernetes experience (preferred)
    - French and English fluent
    - Master's degree in CS or equivalent
    
    Nice to have:
    - FinTech experience
    - Team leadership experience
    
    Responsibilities:
    - Design and implement scalable microservices
    - Mentor junior developers
    - Participate in architecture decisions
    - On-call rotation (1 week per month)
    
    Benefits:
    - 25 days PTO + RTT
    - Health insurance (Alan)
    - Meal vouchers (Swile)
    - MacBook Pro M3
    - Stock options
    
    Apply before: January 30, 2026
    Contact: jobs@fintechstartup.com
    """


async def extract_job(text: str) -> JobDetails | ExtractionFailed:
    """Extract job details from text content.

    Args:
        text: Raw text content from a job posting page

    Returns:
        Structured JobDetails or ExtractionFailed
    """
    result = await job_extraction_agent.run(
        f"Extract job details from this posting:\n\n{text}"
    )
    if isinstance(result.output, ExtractionFailed):
        logger.error("Job extraction failed", reason=result.output.reason)
    else:
        logger.info(
            "Job extraction completed",
            job_company=result.output.company.name,
            job_title=result.output.title,
            usage=result.usage(),
        )
    return result.output


def extract_job_sync(text: str) -> JobDetails | ExtractionFailed:
    """Synchronous version of extract_job."""
    import asyncio

    return asyncio.run(extract_job(text))


# =============================================================================
# CLI Entry Point
# =============================================================================


async def main_extraction(
    job_offers: list[dict[str, str]],
    query: str = "Data analyst",
    location: str = "Lille, France",
    export_dir: Path | None = None,
) -> list[JobDetails | ExtractionFailed]:
    """Extract job offers characteristics using LLM, given a list of job postings.

    Parameters
    ----------
    job_offers : list[dict[str, str]]
        list of raw job posting contents
    query : str, optional
        job type to seek, by default "Data analyst"
    location : str, optional
        job location wished, by default "Lille, France"
    max_results_per_source : int, optional
        maximum number of results to extract per source, by default 1
    export_dir : Path | None, optional
        optional path to export results as text and JSON, by default does not save
    """
    from hireme.utils.common import write_job_offer_to_json

    logger.info(
        "Starting job extraction",
        query=query,
        location=location,
    )
    results: list[JobDetails | ExtractionFailed] = []

    raw_export_dir: Path = Path()
    processed_export_dir: Path = Path()

    if export_dir:
        raw_export_dir = export_dir / "raw"
        processed_export_dir = export_dir / "processed"

        if not processed_export_dir.exists():
            processed_export_dir.mkdir(parents=True, exist_ok=True)
        if not raw_export_dir.exists():
            raw_export_dir.mkdir(parents=True, exist_ok=True)

    for i, posting in enumerate(job_offers):
        url = posting.get("url", "unknown")
        content = posting["content"]

        logger.debug(
            "Processing offer",
            preview_url=url[:URL_PREVIEW],
            index=i + 1,
            total=len(job_offers),
        )
        result = await extract_job(content)

        if isinstance(result, JobDetails):
            if export_dir:
                job_json_path = write_job_offer_to_json(
                    url, result.model_dump(), processed_export_dir
                )
                raw_filename = f"job_{result.model_dump().get('title', 'unknown')}-{result.model_dump().get('company', {}).get('name', 'unknown')}.txt"
                with (export_dir / "raw" / raw_filename).open(
                    "w", encoding="utf-8"
                ) as f:
                    f.write(content)
                logger.debug("Job offer saved", path=job_json_path)
            # print(result.model_dump_json(indent=2))
        results.append(result)

    return results


async def main(
    query: str = "Data analyst",
    location: str = "Lille, France",
    max_results_per_source: int = 1,
    mode: Literal["scrapper", "testing"] = "scrapper",
    export_dir: Path | None = None,
):
    """Test the job extraction agent with a sample posting.
    Deprecated - use the CLI instead
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel(f"Job Extraction Agent - Mode: {mode}", style="bold blue"))
    job_offers: list[dict[str, str]] = []  # list of dict with 'url' and 'content' keys

    if mode == "testing":
        console.print(Panel("Using sample job posting for extraction.", style="yellow"))
        job_offers = [{"url": "sample_url", "content": SAMPLE_POSTING}]

    elif mode == "scrapper":
        console.print(Panel("Extracting job from live job postings.", style="yellow"))
        job_urls = get_job_urls(
            query, location=location, max_results_per_source=max_results_per_source
        )

        console.print(f"Found {len(job_urls)} job URLs to process.")

        for i, url in enumerate(job_urls):
            logger.debug(
                "Fetching offer content from URL",
                preview_url=url[:URL_PREVIEW],
                index=i + 1,
            )

            job_posting = get_job_page(url)

            if job_posting is None:
                logger.error(
                    "Failed to fetch offer content",
                    preview_url=url[:URL_PREVIEW],
                    index=i + 1,
                )
                continue

            job_offers.append({"url": url, "content": job_posting})
            logger.debug(
                "Job offer fetched successfully",
                preview_url=url[:URL_PREVIEW],
                index=i + 1,
            )

    await main_extraction(
        job_offers=job_offers,
        query=query,
        location=location,
        export_dir=export_dir,
    )
