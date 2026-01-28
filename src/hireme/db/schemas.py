"""Pydantic schemas for database models.

These are used for API/CLI responses, separate from SQLAlchemy models.
"""

from datetime import datetime

from pydantic import BaseModel

from hireme.db.database import ApplicationStatus, JobSource

# =============================================================================
# Job Offer Schemas
# =============================================================================


class JobOfferSummary(BaseModel):
    """Summary view of a job offer."""

    id: int
    title: str
    company_name: str
    location: str | None
    source: str
    is_processed: bool
    has_resume: bool = False
    application_status: str | None = None
    discovered_at: datetime

    class Config:
        from_attributes = True


class JobOfferDetail(BaseModel):
    """Detailed view of a job offer."""

    id: int
    title: str
    company_name: str
    location: str | None
    url: str | None
    source: str
    raw_text: str | None
    processed_data: dict | None
    is_processed: bool
    is_archived: bool
    discovered_at: datetime
    processed_at: datetime | None
    resumes_count: int = 0
    application_status: str | None = None

    class Config:
        from_attributes = True


class JobOfferCreate(BaseModel):
    """Schema for creating a job offer."""

    title: str
    company_name: str
    url: str | None = None
    source: JobSource = JobSource.OTHER
    location: str | None = None
    raw_text: str | None = None


# =============================================================================
# Resume Schemas
# =============================================================================


class ResumeSummary(BaseModel):
    """Summary view of a generated resume."""

    id: int
    job_offer_id: int
    profile_name: str
    pdf_path: str | None
    model_used: str | None
    is_selected: bool
    user_rating: int | None
    generated_at: datetime

    class Config:
        from_attributes = True


class ResumeDetail(BaseModel):
    """Detailed view of a generated resume."""

    id: int
    job_offer_id: int
    profile_name: str
    yaml_path: str | None
    pdf_path: str | None
    resume_data: dict | None
    model_used: str | None
    generation_time_seconds: float | None
    tokens_used: int | None
    is_selected: bool
    user_rating: int | None
    user_notes: str | None
    generated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Application Schemas
# =============================================================================


class ApplicationSummary(BaseModel):
    """Summary view of an application."""

    id: int
    job_offer_id: int
    job_title: str | None = None
    company_name: str | None = None
    status: str
    applied_at: datetime | None
    follow_up_date: datetime | None
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationDetail(BaseModel):
    """Detailed view of an application."""

    id: int
    job_offer_id: int
    status: str
    applied_at: datetime | None
    applied_via: str | None
    cover_letter_path: str | None
    resume_used_id: int | None
    follow_up_date: datetime | None
    last_contact_date: datetime | None
    interview_dates: list | None
    response_received: bool
    response_date: datetime | None
    rejection_reason: str | None
    offer_details: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: ApplicationStatus | None = None
    applied_via: str | None = None
    notes: str | None = None
    follow_up_date: datetime | None = None


# =============================================================================
# Stats Schema
# =============================================================================


class ApplicationStats(BaseModel):
    """Statistics about the job search."""

    total_jobs: int
    processed_jobs: int
    total_resumes: int
    not_applied: int
    resume_generated: int
    applied: int
    interview_scheduled: int
    interviewed: int
    offer_received: int
    accepted: int
    rejected: int
    withdrawn: int

    @property
    def application_rate(self) -> float:
        """Percentage of jobs applied to."""
        if self.total_jobs == 0:
            return 0.0
        applied_statuses = (
            self.applied
            + self.interview_scheduled
            + self.interviewed
            + self.offer_received
            + self.accepted
            + self.rejected
        )
        return (applied_statuses / self.total_jobs) * 100

    @property
    def success_rate(self) -> float:
        """Percentage of applications that got interviews."""
        applied_total = self.applied + self.interview_scheduled + self.interviewed
        if applied_total == 0:
            return 0.0
        got_interview = (
            self.interview_scheduled + self.interviewed + self.offer_received
        )
        return (got_interview / applied_total) * 100
