from pydantic import BaseModel, Field

# =============================================================================
# File Content Models
# =============================================================================


class FileContent(BaseModel):
    """Content extracted from a file."""

    filename: str = Field(..., description="Name of the source file")
    file_type: str = Field(..., description="Type of file (pdf, md, txt, yaml)")
    content: str = Field(..., description="Extracted text content")


class UserContext(BaseModel):
    """Complete user context loaded from directory."""

    # Personal info (from structured files like YAML or parsed from notes)
    name: str = Field(default="", description="Full name")
    email: str = Field(default="", description="Email address")
    phone: str | None = Field(default=None, description="Phone number")
    location: str = Field(default="", description="Current location")
    linkedin_username: str | None = Field(default=None, description="LinkedIn username")
    github_username: str | None = Field(default=None, description="GitHub username")
    website: str | None = Field(default=None, description="Personal website URL")

    # Raw file contents for context
    # files: list[FileContent] = Field(
    #     default_factory=list, description="All loaded file contents"
    # )

    # Structured context note (main source of truth)
    context_note: str = Field(
        default="",
        description="Main context note with detailed background information",
    )
