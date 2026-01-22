from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# =============================================================================
# API Configurations
# =============================================================================


class OllamaConfig(BaseSettings):
    """Ollama API configuration."""

    model: str = Field(
        default="qwen2.5:7b-instruct",
        description="The Ollama model to use.",
        alias="OLLAMA_FALLBACK_MODEL",
    )
    base_url: Optional[str] = Field(
        default="http://localhost:11434",
        description="The base URL for the Ollama API.",
        alias="OLLAMA_BASE_URL",
    )
    timeout: Optional[int] = Field(
        default=60,
        description="Timeout in seconds for API requests.",
    )


class OpenAIConfig(BaseSettings):
    """OpenAI API configuration."""

    api_key: str = Field(..., description="The OpenAI API key.")
    model: str = Field("gpt-4", description="The OpenAI model to use.")
    temperature: Optional[float] = Field(
        default=0.7,
        description="Sampling temperature for the model.",
    )
    max_tokens: Optional[int] = Field(
        default=2048,
        description="Maximum number of tokens to generate.",
    )


# class AgentModelsConfig(BaseSettings):
#     """Configuration for models used by different agents."""

#     job_offer_model: str = Field(
#         default="qwen2.5:7b-instruct",
#         description="Model used for job offer extraction.",
#         alias="JOB_OFFER_MODEL",
#     )
#     resume_model: str = Field(
#         default="qwen2.5:7b-instruct",
#         description="Model used for resume generation.",
#         alias="RESUME_MODEL",
#     )


# =============================================================================
# Main Application Config
# =============================================================================


def _create_default_hireme_dir() -> Path:
    dir_path = Path.cwd() / Path(".hireme")
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _create_default_job_offers_dir(hireme_dir: Path) -> Path:
    dir_path = hireme_dir / Path("job_offers")
    dir_path.mkdir(parents=True, exist_ok=True)
    if not (dir_path / "raw").exists():
        (dir_path / "raw").mkdir(parents=True, exist_ok=True)
    if not (dir_path / "processed").exists():
        (dir_path / "processed").mkdir(parents=True, exist_ok=True)
    return dir_path


def _create_default_profile_dir(hireme_dir: Path) -> Path:
    dir_path = hireme_dir / Path("profile")
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


class Config(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="HIREME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama: OllamaConfig = Field(
        default_factory=OllamaConfig,
        description="Configuration for Ollama API.",
    )

    openai: Optional[OpenAIConfig] = Field(
        default=None,
        description="Configuration for OpenAI API.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    assets_dir: Path = Field(
        default_factory=lambda: Path.cwd() / Path("assets"),
        description="Directory to store asset files.",
    )
    # =============================================================================
    # project directories configuration
    # =============================================================================

    hireme_dir: Path = Field(
        default_factory=_create_default_hireme_dir,
        description="Base directory for HireME configurations and data.",
    )

    job_offers_dir: Path = Field(
        default_factory=lambda: _create_default_job_offers_dir(
            _create_default_hireme_dir()
        ),
        description="Directory to store job offers data.",
    )
    profile_dir: Path = Field(
        default_factory=lambda: _create_default_profile_dir(
            _create_default_hireme_dir()
        ),
        description="Directory to store user profile data.",
    )


# Global config instance
cfg = Config()
