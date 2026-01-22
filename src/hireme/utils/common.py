import json
from pathlib import Path

import structlog
import yaml

from hireme.utils.models.models import FileContent, UserContext

logger = structlog.get_logger(logger_name=__name__)


# =============================================================================
# File Loading Functions
# =============================================================================


def load_pdf_content(file_path: Path) -> str:
    """Extract text content from a PDF file.

    Requires pypdf or pdfplumber to be installed.
    """
    try:
        # Try pypdf first (lighter weight)
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    try:
        # Try pdfplumber as fallback
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
    except ImportError:
        logger.warning(
            "No PDF library available. Install pypdf or pdfplumber to read PDFs.",
            file=str(file_path),
        )
        return f"[PDF content could not be extracted: {file_path.name}]"


def load_text_content(file_path: Path) -> str:
    """Load content from a text or markdown file."""
    return file_path.read_text(encoding="utf-8")


def load_yaml_content(file_path: Path) -> tuple[str, dict]:
    """Load content from a YAML file, return both raw and parsed."""
    raw_content = file_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_content)
        return raw_content, parsed or {}
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML", file=str(file_path), error=str(e))
        return raw_content, {}


def load_user_context_from_directory(
    profile_dir: Path,
    context_note_filename: str = "context.md",
    # profile_filename: str = "profile.yaml",
) -> UserContext:
    """Load user context from a directory containing various files.

    Args:
        profile_dir: Path to the directory containing user files
        context_note_filename: Name of the main context note file (md or txt)
        profile_filename: Name of the structured profile YAML file

    Returns:
        UserContext with all loaded information

    Directory structure expected:
        profile_dir/
            context.md          # Main context note (detailed background)
            profile.yaml        # Structured personal info (optional)
            resume.pdf          # Existing resume PDF (optional)
            projects.md         # Project descriptions (optional)
            experience.md       # Work experience details (optional)
            education.md        # Education details (optional)
            skills.txt          # Skills list (optional)
            *.pdf               # Any other PDF files
            *.md                # Any other markdown files
            *.txt               # Any other text files
    """
    if not profile_dir.exists():
        raise FileNotFoundError(f"Profile directory not found: {profile_dir}")

    files: list[FileContent] = []
    context_note = ""
    personal_info = {}

    # Supported file extensions
    supported_extensions = {".pdf", ".md", ".txt", ".yaml", ".yml"}

    # Load all supported files
    for file_path in profile_dir.iterdir():
        logger.debug("Inspecting file", file=file_path.name)
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext not in supported_extensions:
            logger.debug("Skipping unsupported file", file=file_path.name)
            continue

        logger.info("Loading file", file=file_path.name, type=ext)

        try:
            if ext == ".pdf":
                content = load_pdf_content(file_path)
                file_type = "pdf"
            elif ext in {".yaml", ".yml"}:
                content, parsed = load_yaml_content(file_path)
                file_type = "yaml"

                # Extract personal info from profile.yaml
            else:
                content = load_text_content(file_path)
                file_type = "markdown" if ext == ".md" else "text"

                # Check if this is the main context note
                if file_path.name == context_note_filename:
                    context_note = content

            files.append(
                FileContent(
                    filename=file_path.name,
                    file_type=file_type,
                    content=content,
                )
            )

        except Exception as e:
            logger.error("Failed to load file", file=file_path.name, error=str(e))
            continue

    # If no explicit context note, use all markdown files as context
    if not context_note:
        md_contents = [f.content for f in files if f.file_type == "markdown"]
        context_note = "\n\n---\n\n".join(md_contents)

    logger.info(
        "Loaded user context",
        total_files=len(files),
        has_context_note=bool(context_note),
        has_personal_info=bool(personal_info.get("name")),
    )

    # should parse user context from context.md
    return UserContext(
        name=personal_info.get("name", ""),
        email=personal_info.get("email", ""),
        phone=personal_info.get("phone"),
        location=personal_info.get("location", ""),
        linkedin_username=personal_info.get("linkedin_username", ""),
        github_username=personal_info.get("github_username", ""),
        website=personal_info.get("website", ""),
        # files=files,
        context_note=context_note,
    )


def write_job_offer_to_json(url: str, data: dict, export_dir: Path) -> None:
    """Export result data to a JSON file.

    Args:
        url: Source URL of the job offer
        data: Data to export
        export_dir: Directory to save the output files
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = (
        export_dir
        / f"{data.get('title')}-{data.get('company', {'name': ''}).get('name', '')}.json"
    )
    try:
        with export_path.open("w", encoding="utf-8") as f:
            export_data = {"url": url, "data": data}
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        logger.info("Exported result data", path=str(export_path))
    except Exception as e:
        logger.error(
            "Failed to export result data", path=str(export_path), error=str(e)
        )
