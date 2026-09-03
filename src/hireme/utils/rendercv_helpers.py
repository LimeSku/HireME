import subprocess
import sys
from pathlib import Path

import structlog
import yaml

from hireme.config import cfg
from hireme.utils.common import safe_filename_component
from hireme.utils.models.resume_models import TailoredResume

logger = structlog.get_logger(logger_name=__name__)


# =============================================================================
# Path Constants (from config)
# =============================================================================

RENDERCV_ASSETS_DIR = cfg.assets_dir / "rendercv"
DESIGN_TEMPLATE_PATH = RENDERCV_ASSETS_DIR / "design.yaml"
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
    design_data = yaml.safe_load(DESIGN_TEMPLATE_PATH.read_text(encoding="utf-8"))
    logger.info("Loaded RenderCV design template", path=str(DESIGN_TEMPLATE_PATH))
    return design_data or {}


def generate_rendercv_input(resume: TailoredResume, output_dir: Path) -> Path:
    """Generate the complete RenderCV input YAML file."""
    cv_data = convert_to_rendercv_yaml(resume)
    design_data = load_design_template()
    complete_data = {**cv_data, **design_data}

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename_component(resume.name).lower()
    output_file = output_dir / f"{safe_name}_cv.yaml"

    with output_file.open("w", encoding="utf-8") as f:
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
        sys.executable,
        "-m",
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

        pdf_path = output_dir / f"{yaml_path.stem}.pdf"
        if pdf_path.is_file():
            logger.info("Resume PDF generated", path=str(pdf_path))
            return pdf_path
        raise FileNotFoundError(
            f"RenderCV did not generate the expected PDF: {pdf_path}"
        )

    except subprocess.CalledProcessError as e:
        logger.error("RenderCV failed", stderr=e.stderr, stdout=e.stdout)
        raise RuntimeError(f"RenderCV failed: {e.stderr}") from e
