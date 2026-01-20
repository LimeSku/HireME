"""CLI for the Resume Generation Agent.

Generates tailored resumes for job postings using directory-based context loading.
Supports both the new directory-based approach and legacy template-based approach.
"""

from pathlib import Path
from typing import Annotated

import click
import structlog
import typer

from hireme.agents.resume_agent import TailoredResume
from hireme.config import cfg

logger = structlog.get_logger()

app = typer.Typer(name="resume_agent", help="Resume Generation Agent CLI")


@app.command("generate")
def generate(
    job_dir: Annotated[
        Path | None, typer.Option(help="Directory containing job posting files.")
    ] = None,
    profile_dir: Annotated[
        Path | None, typer.Option(help="Directory containing profile files.")
    ] = None,
    output_dir: Annotated[
        Path, typer.Option(help="Directory to save the generated resume files.")
    ] = Path("output/"),
    parse_job: bool = typer.Option(
        False, help="Parse the job posting to extract structured job details."
    ),
):
    """Generate a tailored resume for a job posting.

    Reads a job posting, extracts job details, and generates a tailored
    resume PDF using the user's profile from a directory of files.

    The profile directory should contain:
    - context.md: Main context note with detailed background
    - profile.yaml: Structured personal info (optional)
    - *.pdf: Resume PDFs or other documents
    - *.md/*.txt: Additional notes and descriptions
    """
    import asyncio

    asyncio.run(
        _generate_resume(
            job_dir=job_dir,
            profile_dir=profile_dir,
            output_dir=output_dir,
            parse_job=parse_job,
        )
    )


async def _generate_resume(
    job_dir: Path | None,
    profile_dir: Path | None,
    output_dir: Path,
    parse_job: bool = False,
    # no_pdf: bool,
):
    """Async implementation of resume generation."""
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel

    from hireme.agents.job_agent import JobDetails, extract_job
    from hireme.agents.resume_agent import (
        DEFAULT_PROFILE_DIR,
        generate_rendercv_input,
        load_user_context_from_directory,
        run_rendercv,
        tailor_resume_from_context,
    )

    console = Console()

    # Determine job file path
    if job_dir is None:
        job_dir = cfg.job_offers_dir

    if not job_dir.exists():
        console.print(f"[red]Error: Job directory not found: {job_dir}[/red]")
        console.print("creating defaults...")
        console.print(f"[blue]Creating job offers directory at: {job_dir}[/blue]")
        cfg.job_offers_dir  # Accessing property to create directories
        raise click.Abort()

    if parse_job:
        job_dir = job_dir / "raw"
    else:
        job_dir = job_dir / "processed"
    if not any(job_dir.glob("*.txt")) and not any(job_dir.glob("*.json")):
        console.print(f"[red]Error: No job posting files found in: {job_dir}[/red]")
        raise click.Abort()

    # Determine profile directory
    if profile_dir is None:
        profile_dir = DEFAULT_PROFILE_DIR

    if not profile_dir.exists():
        console.print(f"[red]Error: Profile directory not found: {profile_dir}[/red]")
        console.print(
            "[yellow]Create a 'profile' directory with your context files:[/yellow]"
        )
        console.print("  - context.md: Main context note with your background")
        console.print("  - profile.yaml: Structured personal info (optional)")
        console.print("  - *.pdf: Your existing resumes or documents")
        console.print("  - *.md/*.txt: Additional notes")
        raise click.Abort()

    # Load user context from directory
    console.print(Panel(f"Loading user context from: {profile_dir}", style="blue"))
    user_context = load_user_context_from_directory(profile_dir)
    console.print(
        f"[green]Loaded {len(user_context.files)} files for: "
        f"{user_context.name or 'Unknown'}[/green]"
    )

    # Extract job details
    job_results: list[JobDetails] = []
    if parse_job:
        logger.debug("Loading raw job files from", job_dir=job_dir)
        console.print(Panel("Extracting job details from posting...", style="blue"))
        for job_file in job_dir.glob("*.txt"):
            console.print(f"[blue]Processing job file: {job_file}[/blue]")
            job_text = job_file.read_text()
            job_result = await extract_job(job_text)
            if not isinstance(job_result, JobDetails):
                console.print(f"[red]Job extraction failed: {job_result.reason}[/red]")
                continue
            job_results.append(job_result)
            console.print(
                f"[green]Extracted job: {job_result.title} at {job_result.company.name}[/green]"
            )
    else:
        import json

        logger.debug("Loading processed job files from", job_dir=job_dir)
        for job_file in job_dir.glob("*.json"):
            console.print(f"[blue]Loading already parsed job file: {job_file}[/blue]")
            job_json_list = None
            with job_file.open() as f:
                job_json_list = json.load(f)
            for job_text in job_json_list:
                logger.debug(
                    "Loaded job as json from file",
                    file_path=job_file.as_posix(),
                    job_text=job_text.get("data", ""),
                )
                job_details = JobDetails.model_validate(job_text.get("data", "{}"))
                logger.debug(
                    "Loaded JobDetails Object",
                    file_path=job_file.as_posix(),
                    job_json=job_details,
                )
                job_results.append(job_details)
                console.print(
                    f"[green]Loaded job: {job_details.title} at {job_details.company.name}[/green]"
                )

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate resume
    console.print(Panel("Generating tailored resume...", style="blue"))

    tailored_resumes: list[TailoredResume] = []
    for i, job_result in enumerate(job_results):
        try:
            tailored_resume = await tailor_resume_from_context(user_context, job_result)
            tailored_resumes.append(tailored_resume)
            # Step 3: Generate RenderCV YAML
            resume_output_dir = output_dir / f"resume_{i}/"
            resume_output_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = generate_rendercv_input(tailored_resume, resume_output_dir)
            # Step 4: Run RenderCV to generate PDF
            pdf_path = run_rendercv(yaml_path, resume_output_dir)
            console.print("[green]✓ Resume generated successfully![/green]")
            console.print(f"[blue]PDF saved to: {pdf_path}[/blue]")

        except Exception as e:
            console.print(f"[red]Error generating PDF: {e}[/red]")


@app.command("init")
def init(
    profile_dir: Annotated[
        Path | None, typer.Option(help="Directory to create the profile files in.")
    ] = None,
):
    """Initialize a new profile directory with example files."""
    from rich.console import Console
    from rich.panel import Panel

    from hireme.agents.resume_agent import DEFAULT_PROFILE_DIR

    console = Console()

    if profile_dir is None:
        profile_dir = DEFAULT_PROFILE_DIR

    if profile_dir.exists() and any(profile_dir.iterdir()):
        console.print(
            f"[yellow]Profile directory already exists: {profile_dir}[/yellow]"
        )
        console.print(
            "[yellow]Use --profile-dir to specify a different location.[/yellow]"
        )
        return

    profile_dir.mkdir(parents=True, exist_ok=True)

    # Create example context.md
    example_context = """# Mon Profil Professionnel

## Informations Personnelles
- Nom: [Votre Nom Complet]
- Email: [votre.email@example.com]
- Téléphone: [+33 6 XX XX XX XX]
- Localisation: [Ville, France]
- LinkedIn: [votre-username]
- GitHub: [votre-username]

## Formation

### [Diplôme] - [École/Université]
- Dates: [YYYY-MM] à [YYYY-MM ou present]
- Lieu: [Ville, France]
- Points clés:
  - [Cours pertinent ou spécialisation]
  - [Projet notable]
  - [Mention ou distinction]

### [Autre Diplôme] - [École]
- Dates: [YYYY-MM] à [YYYY-MM]
- Lieu: [Ville, France]
- Points clés:
  - [Point 1]

## Expérience Professionnelle

### [Poste Actuel] - [Entreprise]
- Dates: [YYYY-MM] à present
- Lieu: [Ville, France]
- Responsabilités et réalisations:
  - [Action + résultat quantifié, ex: "Développé une API REST réduisant le temps de réponse de 40%"]
  - [Autre réalisation avec métriques]
  - [Collaboration, leadership, etc.]

### [Poste Précédent] - [Entreprise]
- Dates: [YYYY-MM] à [YYYY-MM]
- Lieu: [Ville, France]
- Responsabilités et réalisations:
  - [Réalisation 1]
  - [Réalisation 2]

## Projets Personnels

### [Nom du Projet]
- Dates: [YYYY-MM] à [YYYY-MM ou present]
- Description: [Brève description du projet et de son objectif]
- Technologies: [Python, FastAPI, React, PostgreSQL, Docker, etc.]
- Points clés:
  - [Fonctionnalité ou réalisation notable]
  - [Impact ou apprentissage]
  - [Lien GitHub si disponible]

### [Autre Projet]
- Dates: [YYYY-MM] à [YYYY-MM]
- Description: [Description]
- Technologies: [Technologies utilisées]
- Points clés:
  - [Point 1]

## Compétences Techniques

### Langages de Programmation
- Python (expert): NumPy, Pandas, FastAPI, Django, asyncio
- JavaScript/TypeScript: React, Node.js, Next.js
- [Autres langages]

### Outils & Technologies
- Cloud: AWS (EC2, S3, Lambda), GCP
- DevOps: Docker, Kubernetes, CI/CD (GitHub Actions)
- Bases de données: PostgreSQL, MongoDB, Redis
- [Autres outils]

### Méthodologies
- Agile/Scrum, TDD, Clean Architecture

## Langues
- Français: Natif
- Anglais: Courant (C1) - [Certification si applicable]
- [Autres langues]

## Centres d'Intérêt
- [Intérêt 1 pertinent pour le domaine]
- [Intérêt 2]

## Notes Additionnelles
[Toute information supplémentaire qui pourrait être pertinente pour certains postes:
motivations, objectifs de carrière, disponibilité, etc.]

---
IMPORTANT: Ce fichier est la source de vérité pour la génération de CV.
Toutes les informations doivent être exactes et vérifiables.
Ne pas inclure d'informations que vous ne pouvez pas justifier en entretien.
"""
    (profile_dir / "context.md").write_text(example_context)

    # Create example profile.yaml
    example_profile = """# Informations personnelles structurées
# Ce fichier est optionnel mais permet une extraction plus fiable des infos de contact

cv:
  name: "Votre Nom Complet"
  email: "votre.email@example.com"
  phone: "+33 6 XX XX XX XX"
  location: "Ville, France"
  social_networks:
    - network: LinkedIn
      username: "votre-username"
    - network: GitHub
      username: "votre-username"
"""
    (profile_dir / "profile.yaml").write_text(example_profile)

    console.print(Panel(f"Profile directory created: {profile_dir}", style="green"))
    console.print("[green]Created files:[/green]")
    console.print(f"  - {profile_dir / 'context.md'}")
    console.print(f"  - {profile_dir / 'profile.yaml'}")
    console.print("\n[yellow]Next steps:[/yellow]")
    console.print("1. Edit context.md with your real information")
    console.print("2. Edit profile.yaml with your contact details")
    console.print("3. Add any PDF resumes or additional documents")
    console.print("4. Run: hireme resume generate")
