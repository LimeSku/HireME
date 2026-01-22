"""Resume agent using Pydantic AI with directory-based context loading.

Takes user information from a directory containing various files (PDFs, text/md notes)
to construct tailored resumes for job offers without hallucinating.
Uses RenderCV for professional PDF generation.
"""

import subprocess
import tempfile
from pathlib import Path

import logfire
import structlog
import yaml
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from hireme.agents.job_agent import JobDetails
from hireme.agents.prompts import RESUME_AGENT_SYSTEM_PROMPT
from hireme.config import cfg
from hireme.utils.common import load_user_context_from_directory
from hireme.utils.models import UserContext
from hireme.utils.providers import get_llm_model

logger = structlog.get_logger(logger_name=__name__)

# =============================================================================
# Path Constants (from config)
# =============================================================================

RENDERCV_ASSETS_DIR = cfg.assets_dir / "rendercv"
DESIGN_TEMPLATE_PATH = RENDERCV_ASSETS_DIR / "design.yaml"
DEFAULT_PROFILE_DIR = cfg.profile_dir

# =============================================================================
# Tailored Resume Models (Output for RenderCV)
# =============================================================================


class TailoredEducation(BaseModel):
    """Education entry tailored for specific job."""

    institution: str = Field(..., description="Exact name of institution from context")
    area: str = Field(..., description="Field of study / Major")
    degree: str = Field(..., description="Degree type (e.g., Master's, Bachelor's)")
    location: str = Field(..., description="Location of the institution")
    start_date: str = Field(..., description="Start date in YYYY-MM format")
    end_date: str = Field(..., description="End date in YYYY-MM format or 'present'")
    highlights: list[str] = Field(
        default_factory=list,
        description="Highlights from context, rewritten for job relevance",
    )


class TailoredExperience(BaseModel):
    """Experience entry tailored for specific job."""

    company: str = Field(..., description="Exact company name from context")
    position: str = Field(..., description="Exact job title from context")
    location: str = Field(..., description="Work location")
    start_date: str = Field(..., description="Start date in YYYY-MM format")
    end_date: str = Field(..., description="End date in YYYY-MM format or 'present'")
    highlights: list[str] = Field(
        description="3-5 bullet points from context, emphasizing job-relevant skills. "
        "Use action verbs and quantify achievements where possible."
    )


class TailoredProject(BaseModel):
    """Project entry tailored for specific job."""

    name: str = Field(..., description="Exact project name from context")
    start_date: str = Field(..., description="Start date in YYYY-MM format")
    end_date: str = Field(..., description="End date in YYYY-MM format or 'present'")
    summary: str | None = Field(default=None, description="Brief project description")
    highlights: list[str] = Field(
        description="Highlights emphasizing technologies and skills relevant to the job"
    )


class TailoredSkill(BaseModel):
    """Skill entry tailored for specific job."""

    label: str = Field(..., description="Skill category")
    details: str = Field(
        description="Skills from context, reordered to prioritize job-relevant ones"
    )


class TailoredResume(BaseModel):
    """Complete tailored resume ready for RenderCV rendering."""

    # Personal info
    name: str
    email: str
    phone: str | None = None
    location: str
    linkedin_username: str | None = None
    github_username: str | None = None

    # Tailored sections
    education: list[TailoredEducation] = Field(
        description="Education entries from context, tailored to job requirements"
    )
    experience: list[TailoredExperience] = Field(
        description="Experience entries from context, rewritten for relevance. "
        "Order by relevance, not just recency."
    )
    projects: list[TailoredProject] = Field(
        description="Most relevant projects from context (max 3-4). "
        "Emphasize matching technologies."
    )
    skills: list[TailoredSkill] = Field(
        description="Skills from context, reorganized for job relevance"
    )

    # Optional tailored summary
    professional_summary: str | None = Field(
        None,
        description="2-3 sentence professional summary tailored to this specific role. "
        "Based ONLY on information from the context files.",
    )


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

resume_agent: Agent[ResumeAgentDeps, TailoredResume] = Agent(
    model=get_llm_model("mistral-nemo:12b"),
    output_type=TailoredResume,
    retries=3,
    deps_type=ResumeAgentDeps,
    system_prompt=RESUME_AGENT_SYSTEM_PROMPT,
)


@resume_agent.system_prompt
async def add_context_from_files(ctx: RunContext[ResumeAgentDeps]) -> str:
    """Inject all user context from files into the system prompt."""
    user = ctx.deps.user_context
    job = ctx.deps.job

    logger.debug(
        "Injecting user & job context into resume_agent",
        name=user.name,
        job=job.title,
        num_files=len(user.files),
    )

    # Build file contents section
    files_section = ""
    for f in user.files:
        files_section += f"""
--- FICHIER: {f.filename} ({f.file_type}) ---
{f.content}
"""

    # Build job requirements section
    required_skills_str = (
        "\n".join([f"  - {s.name} ({s.level})" for s in job.required_skills])
        or "  - Non spécifié"
    )

    responsibilities_str = (
        "\n".join([f"  - {r}" for r in job.responsibilities[:5]]) or "  - Non spécifié"
    )

    selling_points_str = (
        "\n".join([f"  - {p}" for p in job.key_selling_points[:3]])
        or "  - Non spécifié"
    )

    full_context = f"""

================================================================================
TOUS LES FICHIERS DE CONTEXTE
================================================================================
{files_section}

================================================================================
OFFRE D'EMPLOI CIBLE
================================================================================
Poste: {job.title}
Entreprise: {job.company.name} ({job.company.industry or "Industrie inconnue"})
Lieu: {job.location} ({job.work_mode.value})
Niveau: {job.experience_level.value}
Contrat: {", ".join([ct.value for ct in job.contract_type]) or "Non spécifié"}

Compétences requises:
{required_skills_str}

Langues requises:
{chr(10).join(f"  - {lang}" for lang in job.required_languages) or "  - Non spécifié"}

Responsabilités:
{responsibilities_str}

Points à valoriser:
{selling_points_str}

Formation requise: {job.required_education or "Non spécifié"}
================================================================================

RAPPEL: Génère le CV en utilisant UNIQUEMENT les informations ci-dessus.
Ne jamais inventer de contenu non présent dans les fichiers de contexte.
"""
    return full_context


# =============================================================================
# Resume Generation Functions
# =============================================================================


def normalize_date(date_str: str) -> str:
    """Normalize date strings for RenderCV compatibility."""
    if not date_str:
        return ""
    if date_str.lower() in ("present", "current", "now", "ongoing", "aujourd'hui"):
        return "present"
    return str(date_str)


def convert_to_rendercv_yaml(resume: TailoredResume) -> dict:
    """Convert TailoredResume to RenderCV YAML structure."""
    social_networks = []
    if resume.linkedin_username:
        social_networks.append(
            {"network": "LinkedIn", "username": resume.linkedin_username}
        )
    if resume.github_username:
        social_networks.append(
            {"network": "GitHub", "username": resume.github_username}
        )

    sections = {}

    if resume.professional_summary:
        sections["summary"] = [resume.professional_summary]

    if resume.education:
        sections["education"] = [
            {
                "institution": edu.institution,
                "area": edu.area,
                "degree": edu.degree,
                "location": edu.location,
                "start_date": normalize_date(edu.start_date),
                "end_date": normalize_date(edu.end_date),
                "highlights": edu.highlights,
            }
            for edu in resume.education
        ]

    if resume.experience:
        sections["experience"] = [
            {
                "company": exp.company,
                "position": exp.position,
                "location": exp.location,
                "start_date": normalize_date(exp.start_date),
                "end_date": normalize_date(exp.end_date),
                "highlights": exp.highlights,
            }
            for exp in resume.experience
        ]

    if resume.projects:
        sections["projects"] = [
            {
                "name": proj.name,
                "start_date": normalize_date(proj.start_date),
                "end_date": normalize_date(proj.end_date),
                **({"summary": proj.summary} if proj.summary else {}),
                "highlights": proj.highlights,
            }
            for proj in resume.projects
        ]

    if resume.skills:
        sections["skills"] = [
            {"label": skill.label, "details": skill.details} for skill in resume.skills
        ]

    cv_data = {
        "cv": {
            "name": resume.name,
            "location": resume.location,
            "email": resume.email,
            **({"phone": resume.phone} if resume.phone else {}),
            **({"social_networks": social_networks} if social_networks else {}),
            "sections": sections,
        }
    }

    return cv_data


def load_design_template() -> dict:
    """Load the design template from the assets directory."""
    with open(DESIGN_TEMPLATE_PATH, "r") as f:
        design_data = yaml.safe_load(f)
    logger.info("Loaded RenderCV design template", path=str(DESIGN_TEMPLATE_PATH))
    return design_data or {}


def generate_rendercv_input(resume: TailoredResume, output_dir: Path) -> Path:
    """Generate the complete RenderCV input YAML file."""
    cv_data = convert_to_rendercv_yaml(resume)
    design_data = load_design_template()
    complete_data = {**cv_data, **design_data}

    safe_name = resume.name.replace(" ", "_").lower()
    output_file = output_dir / f"{safe_name}_cv.yaml"

    with open(output_file, "w") as f:
        yaml.dump(
            complete_data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    logger.info("Generated RenderCV input file", path=str(output_file))
    return output_file


def run_rendercv(yaml_path: Path, output_dir: Path | None = None) -> Path:
    """Run RenderCV to generate the PDF resume."""
    if output_dir is None:
        output_dir = yaml_path.parent

    cmd = [
        "rendercv",
        "render",
        str(yaml_path.absolute()),
        "--output-folder-name",
        str(output_dir.absolute()) + "/",
        "-pdf",
        str(output_dir.absolute()) + "/" + yaml_path.stem + ".pdf",
        "-typ",
        str(output_dir.absolute()) + "/" + yaml_path.stem + ".typ",
        "-nomd",
        "-nohtml",
        "-nopng",
    ]

    logger.info("Running RenderCV", command=" ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.debug("RenderCV stdout", output=result.stdout)

        pdf_files = list((output_dir).glob("*.pdf"))
        if pdf_files:
            pdf_path = pdf_files[0]
            logger.info("Resume PDF generated", path=str(pdf_path))
            return pdf_path
        else:
            raise FileNotFoundError("RenderCV did not generate a PDF file")

    except subprocess.CalledProcessError as e:
        logger.error("RenderCV failed", stderr=e.stderr, stdout=e.stdout)
        raise RuntimeError(f"RenderCV failed: {e.stderr}") from e


# =============================================================================
# Main API Functions
# =============================================================================


async def tailor_resume_from_context(
    user_context: UserContext,
    job: JobDetails,
) -> TailoredResume:
    """Tailor a resume from user context files for a specific job.

    Args:
        user_context: User context loaded from directory
        job: Structured job details from the job extractor

    Returns:
        A tailored resume based on context files
    """
    context = ResumeAgentDeps(user_context=user_context, job=job)

    result = await resume_agent.run(
        """Génère le CV adapté à partir des fichiers de contexte et de l'offre d'emploi.

RAPPEL CRITIQUE:
- Utilise UNIQUEMENT les informations présentes dans les fichiers de contexte
- Copie EXACTEMENT: noms d'entreprises, écoles, postes, dates, lieux
- Reformule les descriptions pour mettre en avant les compétences pertinentes
- Utilise les mots-clés de l'offre dans les reformulations
- Format des dates: "YYYY-MM" ou "present" (minuscule)
- Si une information manque, OMETS-LA plutôt que de l'inventer

Retourne le CV structuré.""",
        deps=context,
    )

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
    profile_dir = DEFAULT_PROFILE_DIR
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
    console.print(
        f"[green]Loaded {len(user_context.files)} files for: {user_context.name or 'Unknown'}[/green]"
    )

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
