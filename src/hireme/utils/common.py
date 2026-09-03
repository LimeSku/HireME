import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
import yaml
from pydantic import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from hireme.utils.models.models import CandidateProfile, FileContent, UserContext

logger = structlog.get_logger(logger_name=__name__)

SUPPORTED_PROFILE_EXTENSIONS = {".pdf", ".md", ".txt", ".yaml", ".yml"}
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid"}


def safe_filename_component(value: str, fallback: str = "unknown") -> str:
    """Return a bounded filename component without path traversal characters."""
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    return cleaned[:100] or fallback


def normalize_url(url: str) -> str:
    """Normalize a URL while preserving parameters that may identify the resource."""
    parts = urlsplit(url.strip())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in TRACKING_QUERY_KEYS
        ]
    )
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, "")
    )


def load_pdf_content(file_path: Path) -> str:
    """Extract text from a PDF profile document."""
    try:
        reader = PdfReader(file_path)
        return "\n\n".join(
            text for page in reader.pages if (text := page.extract_text())
        )
    except (OSError, PdfReadError) as error:
        raise ValueError(f"Unable to read PDF profile file: {file_path}") from error


def load_text_content(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def load_yaml_content(file_path: Path) -> tuple[str, dict[str, Any]]:
    """Load a YAML mapping and preserve its raw representation."""
    raw_content = file_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_content) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML file: {file_path}") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected a YAML mapping in: {file_path}")
    return raw_content, parsed


def load_user_context_from_directory(profile_dir: Path) -> UserContext:
    """Load and validate a complete candidate profile directory."""
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"Profile directory not found: {profile_dir}")

    profile_path = profile_dir / "profile.yaml"
    if not profile_path.is_file():
        raise FileNotFoundError(f"Required profile file not found: {profile_path}")

    _, profile_data = load_yaml_content(profile_path)
    raw_profile = profile_data.get("profile")
    if not isinstance(raw_profile, dict):
        raise ValueError(f"Missing 'profile' mapping in: {profile_path}")
    try:
        profile = CandidateProfile.model_validate(raw_profile)
    except ValidationError as error:
        raise ValueError(f"Invalid candidate profile: {profile_path}") from error

    missing = [
        field
        for field in ("name", "email", "location")
        if not getattr(profile, field).strip()
    ]
    if missing:
        raise ValueError(f"Missing required profile fields: {', '.join(missing)}")

    files: list[FileContent] = []
    for file_path in sorted(path for path in profile_dir.rglob("*") if path.is_file()):
        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_PROFILE_EXTENSIONS:
            continue
        if extension == ".pdf":
            content, file_type = load_pdf_content(file_path), "pdf"
        elif extension in {".yaml", ".yml"}:
            content, _ = load_yaml_content(file_path)
            file_type = "yaml"
        else:
            content = load_text_content(file_path)
            file_type = "markdown" if extension == ".md" else "text"

        relative_name = str(file_path.relative_to(profile_dir))
        files.append(
            FileContent(filename=relative_name, file_type=file_type, content=content)
        )

    logger.info("Loaded user context", total_files=len(files))
    return UserContext(profile=profile, files=files)


def write_job_offer_to_json(url: str, data: dict[str, Any], export_dir: Path) -> Path:
    """Export one structured job offer and return its path."""
    export_dir.mkdir(parents=True, exist_ok=True)
    company = data.get("company") or {}
    filename = "-".join(
        (
            safe_filename_component(str(data.get("title", "unknown"))),
            safe_filename_component(str(company.get("name", "unknown"))),
        )
    )
    export_path = export_dir / f"{filename}.json"
    export_path.write_text(
        json.dumps({"url": url, "data": data}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Exported result data", path=str(export_path))
    return export_path
