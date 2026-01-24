"""Database models for HireME application.

Simple SQLite-based database for tracking:
- Downloaded job offers (raw & processed)
- Generated resumes per job
- Application status and history
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
)

from hireme.config import cfg

# =============================================================================
# Enums
# =============================================================================


class ApplicationStatus(str, Enum):
    """Status of a job application."""

    NOT_APPLIED = "not_applied"
    RESUME_GENERATED = "resume_generated"
    APPLIED = "applied"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    OFFER_RECEIVED = "offer_received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class JobSource(str, Enum):
    """Source where the job was found."""

    INDEED = "indeed"
    LINKEDIN = "linkedin"
    WELCOME_TO_THE_JUNGLE = "welcome_to_the_jungle"
    MANUAL = "manual"
    OTHER = "other"


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class JobOffer(Base):
    """A job offer with all its data and processing status."""

    __tablename__ = "job_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source information
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default=JobSource.OTHER.value)

    # Job identification (used for deduplication)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Raw data storage
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Processed data (JSON blob of JobDetails)
    processed_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    processed_file_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    resumes: Mapped[list["GeneratedResume"]] = relationship(
        "GeneratedResume", back_populates="job_offer", cascade="all, delete-orphan"
    )
    application: Mapped[Optional["Application"]] = relationship(
        "Application", back_populates="job_offer", uselist=False
    )

    def __repr__(self) -> str:
        return f"<JobOffer(id={self.id}, title='{self.title}', company='{self.company_name}')>"


class GeneratedResume(Base):
    """A resume generated for a specific job offer and profile."""

    __tablename__ = "generated_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    job_offer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_offers.id"), nullable=False
    )
    profile_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="default"
    )

    # Generated files
    yaml_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Resume data (JSON blob of TailoredResume)
    resume_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Generation metadata
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    generation_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    # Quality/feedback
    user_rating: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 1-5 stars
    user_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_selected: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Selected version for application

    # Relationships
    job_offer: Mapped["JobOffer"] = relationship("JobOffer", back_populates="resumes")

    def __repr__(self) -> str:
        return f"<GeneratedResume(id={self.id}, job_id={self.job_offer_id}, profile='{self.profile_name}')>"


class Application(Base):
    """Tracking a job application."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    job_offer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_offers.id"), nullable=False, unique=True
    )

    # Application status
    status: Mapped[str] = mapped_column(
        String(50), default=ApplicationStatus.NOT_APPLIED.value
    )

    # Application details
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_via: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # email, website, linkedin, etc.
    cover_letter_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    resume_used_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("generated_resumes.id"), nullable=True
    )

    # Follow-up tracking
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Interview tracking
    interview_dates: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # List of interview dates/notes

    # Outcome
    response_received: Mapped[bool] = mapped_column(Boolean, default=False)
    response_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offer_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # Relationships
    job_offer: Mapped["JobOffer"] = relationship(
        "JobOffer", back_populates="application"
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, job_id={self.job_offer_id}, status='{self.status}')>"


# =============================================================================
# Database Manager
# =============================================================================


class DatabaseManager:
    """Manager for database operations."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = cfg.hireme_dir / "hireme.db"

        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self._create_tables()

    def _create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return Session(self.engine)

    # =========================================================================
    # Job Offer Operations
    # =========================================================================

    def add_job_offer(
        self,
        title: str,
        company_name: str,
        url: str | None = None,
        source: JobSource = JobSource.OTHER,
        location: str | None = None,
        raw_text: str | None = None,
        raw_file_path: str | None = None,
    ) -> JobOffer:
        """Add a new job offer to the database."""
        with self.get_session() as session:
            # Check for duplicates
            existing = (
                session.query(JobOffer)
                .filter(
                    JobOffer.title == title,
                    JobOffer.company_name == company_name,
                    JobOffer.is_archived == False,
                )
                .first()
            )
            if existing:
                return existing

            job = JobOffer(
                title=title,
                company_name=company_name,
                url=url,
                source=source.value,
                location=location,
                raw_text=raw_text,
                raw_file_path=raw_file_path,
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_job_processed(
        self,
        job_id: int,
        processed_data: dict,
        processed_file_path: str | None = None,
    ) -> JobOffer | None:
        """Mark a job offer as processed with extracted data."""
        with self.get_session() as session:
            job = session.get(JobOffer, job_id)
            if job:
                job.processed_data = processed_data
                job.processed_file_path = processed_file_path
                job.is_processed = True
                job.processed_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(job)
            return job

    def get_all_jobs(
        self, include_archived: bool = False, only_processed: bool = False
    ) -> list[JobOffer]:
        """Get all job offers."""
        with self.get_session() as session:
            query = session.query(JobOffer).options(
                selectinload(JobOffer.resumes),
                selectinload(JobOffer.application),
            )
            if not include_archived:
                query = query.filter(JobOffer.is_archived == False)
            if only_processed:
                query = query.filter(JobOffer.is_processed == True)
            jobs = query.order_by(JobOffer.discovered_at.desc()).all()
            # Detach from session to allow access after session closes
            session.expunge_all()
            return jobs

    def get_job_by_id(self, job_id: int) -> JobOffer | None:
        """Get a job offer by ID."""
        with self.get_session() as session:
            job = (
                session.query(JobOffer)
                .options(
                    selectinload(JobOffer.resumes),
                    selectinload(JobOffer.application),
                )
                .filter(JobOffer.id == job_id)
                .first()
            )
            if job:
                session.expunge(job)
            return job

    def search_jobs(self, query: str, include_archived: bool = False) -> list[JobOffer]:
        """Search jobs by title or company name."""
        with self.get_session() as session:
            q = (
                session.query(JobOffer)
                .options(
                    selectinload(JobOffer.resumes),
                    selectinload(JobOffer.application),
                )
                .filter(
                    (JobOffer.title.ilike(f"%{query}%"))
                    | (JobOffer.company_name.ilike(f"%{query}%"))
                )
            )
            if not include_archived:
                q = q.filter(JobOffer.is_archived == False)
            jobs = q.all()
            session.expunge_all()
            return jobs

    def archive_job(self, job_id: int) -> bool:
        """Archive a job offer."""
        with self.get_session() as session:
            job = session.get(JobOffer, job_id)
            if job:
                job.is_archived = True
                session.commit()
                return True
            return False

    # =========================================================================
    # Resume Operations
    # =========================================================================

    def add_generated_resume(
        self,
        job_offer_id: int,
        profile_name: str = "default",
        resume_data: dict | None = None,
        yaml_path: str | None = None,
        pdf_path: str | None = None,
        model_used: str | None = None,
        generation_time_seconds: float | None = None,
        tokens_used: int | None = None,
    ) -> GeneratedResume:
        """Add a generated resume to the database."""
        with self.get_session() as session:
            resume = GeneratedResume(
                job_offer_id=job_offer_id,
                profile_name=profile_name,
                resume_data=resume_data,
                yaml_path=yaml_path,
                pdf_path=pdf_path,
                model_used=model_used,
                generation_time_seconds=generation_time_seconds,
                tokens_used=tokens_used,
            )
            session.add(resume)
            session.commit()
            session.refresh(resume)
            return resume

    def get_resumes_for_job(self, job_id: int) -> list[GeneratedResume]:
        """Get all resumes generated for a job."""
        with self.get_session() as session:
            return (
                session.query(GeneratedResume)
                .filter(GeneratedResume.job_offer_id == job_id)
                .order_by(GeneratedResume.generated_at.desc())
                .all()
            )

    def select_resume(self, resume_id: int) -> bool:
        """Mark a resume as the selected version for application."""
        with self.get_session() as session:
            resume = session.get(GeneratedResume, resume_id)
            if resume:
                # Deselect other resumes for this job
                session.query(GeneratedResume).filter(
                    GeneratedResume.job_offer_id == resume.job_offer_id
                ).update({GeneratedResume.is_selected: False})

                resume.is_selected = True
                session.commit()
                return True
            return False

    def rate_resume(
        self, resume_id: int, rating: int, notes: str | None = None
    ) -> bool:
        """Rate a generated resume."""
        with self.get_session() as session:
            resume = session.get(GeneratedResume, resume_id)
            if resume:
                resume.user_rating = max(1, min(5, rating))  # Clamp to 1-5
                if notes:
                    resume.user_notes = notes
                session.commit()
                return True
            return False

    # =========================================================================
    # Application Operations
    # =========================================================================

    def create_application(
        self,
        job_offer_id: int,
        status: ApplicationStatus = ApplicationStatus.NOT_APPLIED,
    ) -> Application:
        """Create an application record for a job."""
        with self.get_session() as session:
            # Check if application already exists
            existing = (
                session.query(Application)
                .filter(Application.job_offer_id == job_offer_id)
                .first()
            )
            if existing:
                return existing

            app = Application(
                job_offer_id=job_offer_id,
                status=status.value,
            )
            session.add(app)
            session.commit()
            session.refresh(app)
            return app

    def update_application_status(
        self,
        job_offer_id: int,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> Application | None:
        """Update the status of an application."""
        with self.get_session() as session:
            app = (
                session.query(Application)
                .filter(Application.job_offer_id == job_offer_id)
                .first()
            )
            if app:
                app.status = status.value
                if status == ApplicationStatus.APPLIED:
                    app.applied_at = datetime.now(timezone.utc)
                if notes:
                    app.notes = (
                        app.notes or ""
                    ) + f"\n[{datetime.now(timezone.utc)}] {notes}"
                app.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(app)
            return app

    def get_applications_by_status(
        self, status: ApplicationStatus
    ) -> list[Application]:
        """Get all applications with a specific status."""
        with self.get_session() as session:
            return (
                session.query(Application)
                .filter(Application.status == status.value)
                .all()
            )

    def get_application_stats(self) -> dict:
        """Get statistics about applications."""
        with self.get_session() as session:
            stats = {}
            for status in ApplicationStatus:
                count = (
                    session.query(Application)
                    .filter(Application.status == status.value)
                    .count()
                )
                stats[status.value] = count
            stats["total_jobs"] = session.query(JobOffer).count()
            stats["processed_jobs"] = (
                session.query(JobOffer).filter(JobOffer.is_processed == True).count()
            )
            stats["total_resumes"] = session.query(GeneratedResume).count()
            return stats


# =============================================================================
# Global database instance
# =============================================================================

_db: DatabaseManager | None = None


def get_db() -> DatabaseManager:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db
