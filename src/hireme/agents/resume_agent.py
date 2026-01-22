"""Resume agent using Pydantic AI with directory-based context loading.

Takes user information from a directory containing various files (PDFs, text/md notes)
to construct tailored resumes for job offers without hallucinating.
Uses RenderCV for professional PDF generation.
"""

import tempfile
from pathlib import Path

import structlog
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry

from hireme.agents.job_agent import JobDetails
from hireme.config import cfg
from hireme.utils.common import load_user_context_from_directory
from hireme.utils.models.models import UserContext
from hireme.utils.models.resume_models import GenerationFailed, TailoredResume
from hireme.utils.providers import get_llm_model
from hireme.utils.rendercv_helpers import (
    generate_rendercv_input,
    run_rendercv,
)

logger = structlog.get_logger(logger_name=__name__)


# =============================================================================
# Agent Context
# =============================================================================


class ResumeAgentDeps(BaseModel):
    """Context for the resume tailoring agent."""

    user_context: UserContext
    job: JobDetails


# =============================================================================
# Resume Agent Definition
# =============================================================================

# resume_agent: Agent[ResumeAgentDeps, TailoredResume] = Agent(
resume_agent: Agent[None, TailoredResume | GenerationFailed] = Agent(
    model=get_llm_model("mistral-nemo:12b"),
    output_type=TailoredResume | GenerationFailed,
    retries=3,
    system_prompt="""
You are an expert resume writer specializing in tailoring CVs to specific job postings.

Your task is to create a professional, ATS-friendly resume that highlights the candidate's 
most relevant qualifications for the target position.

CRITICAL RULES:
- Use ONLY information from the provided user context - NEVER hallucinate or invent details
- Copy EXACTLY: company names, institutions, job titles, dates, and locations from context
- Rewrite bullet points to emphasize skills and achievements relevant to the job posting
- Incorporate keywords from the job description naturally in your reformulations
- Prioritize and reorder sections based on relevance to the target role
- Date format must be "YYYY-MM" or "present" (lowercase)
- If information is missing from context, OMIT it rather than making it up

GUIDELINES:
- Quantify achievements with metrics when available in context
- Use strong action verbs (Led, Developed, Implemented, Achieved, etc.)
- Tailor the professional summary to match the specific role
- Highlight technical skills that match the job requirements
- Keep descriptions concise and impactful (3-5 bullet points per role)
- Ensure the resume passes ATS systems by using relevant keywords
- Order experiences and projects by relevance, not just chronologically

Return the structured, tailored resume ready for rendering.
""",
)


@resume_agent.output_validator
async def validate_resume(
    output: TailoredResume | GenerationFailed,
) -> TailoredResume | GenerationFailed:
    if isinstance(output, GenerationFailed):
        raise ModelRetry(f"Generation failed: {output.reason}")
    else:
        return output


# =============================================================================
# Main API Functions
# =============================================================================


async def tailor_resume_from_context(
    user_context: UserContext,
    job: JobDetails,
) -> TailoredResume:
    """Tailor a resume from user context files for a specific job.

    Args:
        user_context: User informations
        job: Structured job details from the job extractor

    Returns:
        Structured TailoredResume based on given information
    """
    # context = ResumeAgentDeps(user_context=user_context, job=job)

    result = await resume_agent.run(
        f"""
Generate a tailored resume based on the following user context and job posting:\n\n
Contexte utilisateur:
```json
{user_context.model_dump_json(indent=2)}
```

Offre d'emploi cible:
```json
{job.model_dump_json(indent=2)}
```

""",
        # deps=context,
    )

    if isinstance(result.output, GenerationFailed):
        logger.warning("Resume generation failed", reason=result.output.reason)
        raise RuntimeError(f"Resume generation failed: {result.output.reason}")
    logger.info("Resume tailoring completed", usage=result.usage())
    return result.output


async def generate_resume_from_directory(
    profile_dir: Path,
    job: JobDetails,
    output_dir: Path | None = None,
    context_note_filename: str = "context.md",
) -> tuple[TailoredResume, Path]:
    """Complete pipeline: load context, tailor resume, and generate PDF.

    Args:
        profile_dir: Directory containing user profile files
        job: Structured job details from the job extractor
        output_dir: Optional output directory for generated files
        context_note_filename: Name of the main context note file
        profile_filename: Name of the structured profile YAML file

    Returns:
        Tuple of (tailored resume, path to generated PDF)
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="hireme_resume_"))

    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load user context from directory
    user_context = load_user_context_from_directory(
        profile_dir=profile_dir,
        context_note_filename=context_note_filename,
    )

    # Step 2: Tailor the resume
    tailored_resume = await tailor_resume_from_context(user_context, job)

    # Step 3: Generate RenderCV YAML
    yaml_path = generate_rendercv_input(tailored_resume, output_dir)

    # Step 4: Run RenderCV to generate PDF
    pdf_path = run_rendercv(yaml_path, output_dir)

    return tailored_resume, pdf_path


def generate_resume_from_directory_sync(
    profile_dir: Path,
    job: JobDetails,
    output_dir: Path | None = None,
    context_note_filename: str = "context.md",
    profile_filename: str = "profile.yaml",
) -> tuple[TailoredResume, Path]:
    """Synchronous version of generate_resume_from_directory."""
    import asyncio

    return asyncio.run(
        generate_resume_from_directory(
            profile_dir, job, output_dir, context_note_filename
        )
    )


# =============================================================================
# CLI Entry Point
# =============================================================================


# async def load_profile_from_directory(profile_dir: Path) -> UserContext:
#     """Load user context from a profile directory."""
#     user_context = load_user_context_from_directory(profile_dir)
#     return user_context


async def generate_resume(
    candidate_profile: UserContext, structured_job: JobDetails, output_dir: Path
):
    tailored_resume = await tailor_resume_from_context(
        user_context=candidate_profile, job=structured_job
    )
    yaml_path = generate_rendercv_input(tailored_resume, output_dir)
    pdf_path = run_rendercv(yaml_path, output_dir)
    return tailored_resume, pdf_path


async def main():
    """Test the resume agent with sample data.
    deprecated - use the CLI instead
    """

    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel

    from hireme.agents.job_agent import extract_job

    console = Console()

    # Load job posting
    job_file = Path(__file__).parent.parent.parent.parent / "jobs" / "last_job.txt"
    if not job_file.exists():
        console.print(f"[red]Job file not found: {job_file}[/red]")
        return

    job_posting = job_file.read_text()

    # Load user context from profile directory
    profile_dir = cfg.profile_dir
    if not profile_dir.exists():
        console.print(f"[yellow]Profile directory not found: {profile_dir}[/yellow]")
        console.print("[yellow]Creating example profile directory...[/yellow]")
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Create example context.md
        example_context = """# Mon Profil Professionnel

## Informations Personnelles
- Nom: [Votre Nom]
- Email: [votre.email@example.com]
- Téléphone: [+33 6 XX XX XX XX]
- Localisation: [Ville, France]
- LinkedIn: [votre-username]
- GitHub: [votre-username]

## Formation
### [Diplôme] - [École]
- Dates: [YYYY-MM] à [YYYY-MM ou present]
- Lieu: [Ville, France]
- Points clés:
  - [Point 1]
  - [Point 2]

## Expérience Professionnelle
### [Poste] - [Entreprise]
- Dates: [YYYY-MM] à [YYYY-MM ou present]
- Lieu: [Ville, France]
- Responsabilités et réalisations:
  - [Réalisation 1 avec métriques si possible]
  - [Réalisation 2]

## Projets
### [Nom du Projet]
- Dates: [YYYY-MM] à [YYYY-MM]
- Description: [Brève description]
- Technologies: [Tech1, Tech2, Tech3]
- Points clés:
  - [Réalisation 1]
  - [Réalisation 2]

## Compétences
- Langages: [Python, JavaScript, etc.]
- Frameworks: [FastAPI, React, etc.]
- Outils: [Git, Docker, etc.]
- Langues: [Français (natif), Anglais (courant), etc.]

## Notes Additionnelles
[Toute information supplémentaire pertinente pour les recruteurs]
"""
        (profile_dir / "context.md").write_text(example_context)
        console.print(f"[green]Created example context.md in {profile_dir}[/green]")
        console.print("[yellow]Please fill in your information and run again.[/yellow]")
        return

    console.print(Panel(f"Loading user context from: {profile_dir}", style="blue"))
    user_context = load_user_context_from_directory(profile_dir)
    # console.print(
    #     f"[green]Loaded {len(user_context.files)} files for: {user_context.name or 'Unknown'}[/green]"
    # )

    # Extract job details
    console.print(Panel("Extracting job details from posting...", style="blue"))
    job_result = await extract_job(job_posting)

    if not isinstance(job_result, JobDetails):
        console.print(f"[red]Job extraction failed: {job_result.reason}[/red]")
        return

    console.print(
        f"[green]Extracted job: {job_result.title} at {job_result.company.name}[/green]"
    )

    # Generate tailored resume
    console.print(Panel("Generating tailored resume...", style="blue"))

    output_dir = Path("./output/resumes")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        tailored_resume, pdf_path = await generate_resume_from_directory(
            profile_dir=profile_dir,
            job=job_result,
            output_dir=output_dir,
        )

        console.print("[green]✓ Resume generated successfully![/green]")
        console.print(f"[blue]PDF saved to: {pdf_path}[/blue]")

        console.print(Panel("Tailored Resume Preview:", style="green"))
        rprint(tailored_resume.model_dump_json(indent=2))

    except Exception as e:
        console.print(f"[red]Error generating resume: {e}[/red]")
        logger.exception("Resume generation failed", e=e)

        # Still show the tailored resume even if PDF generation fails
        console.print(
            Panel("Attempting to show tailored resume without PDF...", style="yellow")
        )
        tailored_resume = await tailor_resume_from_context(user_context, job_result)
        rprint(tailored_resume.model_dump_json(indent=2))


# should have a fct to run with job offersas arguments to not repull them

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
