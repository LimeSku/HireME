from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import DirectoryPath, Field, computed_field, model_validator
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
        default="http://localhost:11434/v1",
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

    project_root: Path = Field(
        default=Path.cwd(),
        description="Root directory for HireME project.",
    )

    assets_dir: Path = Field(
        default=Path.cwd() / "assets",
        description="Directory to store asset files.",
    )
    prompts_dir: Path = Field(
        default=Path.cwd() / "assets" / "prompts",
        description="Directory to store prompt templates.",
    )
    # =============================================================================
    # project directories configuration
    # =============================================================================

    hireme_dir: Path = Field(
        default=Path.cwd() / ".hireme",
        description="Directory to store job offers data.",
    )
    job_offers_dir: Path = Field(
        default=Path.cwd() / ".hireme" / "job_offers",
        description="Directory to store job offers data.",
    )

    profiles_dir: Path = Field(
        default=Path.cwd() / ".hireme" / "profiles",
        description="Directory to store different user profiles data.",
    )

    default_profile_dir: Path = Field(
        default=Path.cwd() / ".hireme" / "profiles" / "default",
        description="Profile directory used by default.",
        alias="HIREME_DEFAULT_PROFILE_PATH",
    )

    @model_validator(mode="after")
    def create_dirs(self):
        dirs_to_create: list[Path] = [
            self.hireme_dir,
            self.job_offers_dir,
            self.job_offers_dir / "raw",
            self.job_offers_dir / "processed",
            self.default_profile_dir,
            self.profiles_dir,
        ]
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
        return self


# Global config instance
cfg = Config()
# print("Configuration loaded:")
# for field_name, field_value in cfg.model_dump().items():
#     print(f"\t{field_name}: {field_value}")
