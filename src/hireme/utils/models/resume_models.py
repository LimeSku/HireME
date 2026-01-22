from pydantic import BaseModel, Field


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


class GenerationFailed(BaseModel):
    """When resume generation fails."""

    reason: str = Field(..., description="Why generation failed")
