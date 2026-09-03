from pydantic import BaseModel, ConfigDict, Field


class FileContent(BaseModel):
    """Content loaded from a candidate profile file."""

    filename: str
    file_type: str
    content: str


class CandidateProfile(BaseModel):
    """Structured identity used as immutable resume data."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = ""
    email: str = ""
    phone: str | None = None
    location: str = ""
    linkedin_username: str | None = Field(default=None, alias="linkedin")
    github_username: str | None = Field(default=None, alias="github")
    website: str | None = None


class UserContext(BaseModel):
    """Complete, source-backed candidate context."""

    profile: CandidateProfile
    context_note: str = ""
    files: list[FileContent] = Field(default_factory=list)

    def source_text(self) -> str:
        return "\n\n".join(file.content for file in self.files)
